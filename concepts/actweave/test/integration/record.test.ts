import { describe, expect, it } from "vitest";
import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { MockLanguageModelV3, convertArrayToReadableStream } from "ai/test";
import type { LanguageModelV3GenerateResult, LanguageModelV3StreamPart } from "@ai-sdk/provider";
import { z } from "zod";

import { createRecorder } from "../../src/record/recorder.js";
import { recordModel } from "../../src/record/model.js";
import { recordTools } from "../../src/record/tools.js";
import { canonicalEventLine, validateLedgerLifecycle } from "../../src/ledger/index.js";
import { checkLedger } from "../../src/check/index.js";

const toolCallResponse: LanguageModelV3GenerateResult = {
  content: [
    { type: "tool-call", toolCallId: "call-1", toolName: "lookupOrder", input: JSON.stringify({ orderId: "123" }) },
  ],
  finishReason: { unified: "tool-calls", raw: "tool_calls" },
  usage: { inputTokens: 10, outputTokens: 5, totalTokens: 15 },
  warnings: [],
};

const finalResponse: LanguageModelV3GenerateResult = {
  content: [{ type: "text", text: "Order 123 cannot be refunded." }],
  finishReason: { unified: "stop", raw: "stop" },
  usage: { inputTokens: 20, outputTokens: 8, totalTokens: 28 },
  warnings: [],
};

function scriptedModel(responses: LanguageModelV3GenerateResult[]): MockLanguageModelV3 {
  let call = 0;
  return new MockLanguageModelV3({
    doGenerate: async () => {
      const response = responses[call++];
      if (!response) {
        throw new Error(`scripted model exhausted after ${responses.length} calls`);
      }
      return response;
    },
  });
}

type RecordedRun = Awaited<ReturnType<ReturnType<typeof createRecorder>["close"]>>;

async function recordRefundRun(): Promise<RecordedRun> {
  const recorder = createRecorder({ deterministic: true });
  const agent = new ToolLoopAgent({
    model: recordModel(scriptedModel([toolCallResponse, finalResponse]), recorder),
    instructions: "Resolve refunds.",
    tools: recordTools(
      {
        lookupOrder: tool({
          description: "Look up an order",
          inputSchema: z.object({ orderId: z.string() }),
          execute: async ({ orderId }: { orderId: string }) => ({ orderId, refundable: false }),
        }),
      },
      recorder,
      { risk: { lookupOrder: "read" } },
    ),
    stopWhen: stepCountIs(5),
  });

  await recorder.run("Can order 123 be refunded?", () => agent.generate({ prompt: "Can order 123 be refunded?" }), {
    agentName: "support",
  });
  return recorder.close();
}

describe("recordModel + recordTools", () => {
  it("records the canonical event sequence for a two-step tool run", async () => {
    const { events } = await recordRefundRun();

    expect(events.map((event) => event.type)).toEqual([
      "run.started",
      "model.called",
      "model.completed",
      "tool.called",
      "tool.completed",
      "model.called",
      "model.completed",
      "run.completed",
    ]);

    expect(validateLedgerLifecycle(events).ok).toBe(true);
    checkLedger(events)
      .completed()
      .noErrors()
      .called("lookupOrder")
      .calledWith("lookupOrder", { orderId: "123" })
      .calledTimes("lookupOrder", 1)
      .validLifecycle();
  });

  it("captures a hashed request with normalized prompt and tools", async () => {
    const { events } = await recordRefundRun();
    const modelCalls = events.filter((event) => event.type === "model.called");

    expect(modelCalls).toHaveLength(2);
    for (const call of modelCalls) {
      expect(call.request?.hash).toMatch(/^sha256:[0-9a-f]{64}$/);
      expect(call.request?.provider).toBe("mock-provider");
      expect(call.request?.modelId).toBe("mock-model-id");
    }

    const firstRequest = modelCalls[0].request;
    expect(firstRequest?.tools).toEqual([
      expect.objectContaining({
        name: "lookupOrder",
        description: "Look up an order",
        inputSchema: expect.not.objectContaining({ $schema: expect.anything() }),
      }),
    ]);
    // step-2 request includes the tool exchange, so the hash must differ
    expect(modelCalls[1].request?.hash).not.toBe(modelCalls[0].request?.hash);
  });

  it("captures model responses verbatim with unified finishReason and usage", async () => {
    const { events } = await recordRefundRun();
    const completions = events.filter((event) => event.type === "model.completed");

    expect(completions[0].modelResponse).toMatchObject({
      finishReason: "tool-calls",
      usage: { inputTokens: 10, outputTokens: 5, totalTokens: 15 },
      provider: "mock-provider",
    });
    expect(completions[0].modelResponse?.content).toEqual([
      { type: "tool-call", toolCallId: "call-1", toolName: "lookupOrder", input: JSON.stringify({ orderId: "123" }) },
    ]);
    expect(completions[0].modelResponse?.raw).toBeUndefined();
    expect(completions[1].output).toBe("Order 123 cannot be refunded.");
  });

  it("correlates tool events by the SDK toolCallId", async () => {
    const { events } = await recordRefundRun();
    const toolCalled = events.find((event) => event.type === "tool.called");
    const toolCompleted = events.find((event) => event.type === "tool.completed");

    expect(toolCalled?.callId).toBe("call-1");
    expect(toolCompleted?.callId).toBe("call-1");
    expect(toolCompleted?.replay).toEqual({ kind: "tool", sideEffect: false });
    expect(toolCompleted?.output).toEqual({ orderId: "123", refundable: false });
  });

  it("re-recording the same run produces byte-identical fixture lines", async () => {
    const first = (await recordRefundRun()).events.map((event) => canonicalEventLine(event));
    const second = (await recordRefundRun()).events.map((event) => canonicalEventLine(event));
    expect(second).toEqual(first);
  });

  it("redacts secrets that pass through tool outputs", async () => {
    const recorder = createRecorder({ deterministic: true });
    const tools = recordTools(
      {
        fetchConfig: {
          description: "Fetch config",
          inputSchema: z.object({}),
          execute: async () => ({ apiKey: "sk-abcdefghijklmnopqrstuvwxyz", region: "us" }),
        },
      },
      recorder,
    );
    await (tools.fetchConfig as { execute: (input: unknown, options?: unknown) => Promise<unknown> }).execute(
      {},
      { toolCallId: "call-secret" },
    );

    const completed = recorder.events().find((event) => event.type === "tool.completed");
    expect(completed?.output).toMatchObject({ apiKey: "[REDACTED]" });
    expect(completed?.redaction?.count).toBeGreaterThan(0);
  });

  it("records streamed runs by consolidating parts at stream end", async () => {
    const recorder = createRecorder({ deterministic: true });
    const streamParts: LanguageModelV3StreamPart[] = [
      { type: "stream-start", warnings: [] },
      { type: "text-start", id: "t1" },
      { type: "text-delta", id: "t1", delta: "Order 123 " },
      { type: "text-delta", id: "t1", delta: "cannot be refunded." },
      { type: "text-end", id: "t1" },
      {
        type: "finish",
        finishReason: { unified: "stop", raw: "stop" },
        usage: { inputTokens: 9, outputTokens: 7, totalTokens: 16 },
      },
    ];
    const model = recordModel(
      new MockLanguageModelV3({
        doStream: async () => ({ stream: convertArrayToReadableStream(streamParts) }),
      }),
      recorder,
    );

    const agent = new ToolLoopAgent({
      model,
      instructions: "Answer.",
      tools: {},
      stopWhen: stepCountIs(3),
    });

    const result = await agent.stream({ prompt: "Can order 123 be refunded?" });
    let streamedText = "";
    for await (const chunk of result.textStream) {
      streamedText += chunk;
    }
    // flush() appends model.completed asynchronously after the stream ends
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(streamedText).toBe("Order 123 cannot be refunded.");
    const completed = recorder.events().find((event) => event.type === "model.completed");
    expect(completed?.modelResponse?.content).toEqual([{ type: "text", text: "Order 123 cannot be refunded." }]);
    expect(completed?.modelResponse?.finishReason).toBe("stop");
    expect(completed?.modelResponse?.usage).toEqual({ inputTokens: 9, outputTokens: 7, totalTokens: 16 });
  });

  it("records model failures as model.failed and rethrows", async () => {
    const recorder = createRecorder({ deterministic: true });
    const model = recordModel(
      new MockLanguageModelV3({
        doGenerate: async () => {
          throw new Error("provider unavailable");
        },
      }),
      recorder,
    );

    await expect(model.doGenerate({ prompt: [] } as never)).rejects.toThrow("provider unavailable");
    const failed = recorder.events().find((event) => event.type === "model.failed");
    expect(failed?.error?.message).toBe("provider unavailable");
    expect(failed?.callId).toBe(recorder.events().find((event) => event.type === "model.called")?.callId);
  });
});
