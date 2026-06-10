import { describe, expect, it } from "vitest";
import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { MockLanguageModelV3 } from "ai/test";
import type { LanguageModelV3, LanguageModelV3GenerateResult } from "@ai-sdk/provider";
import { z } from "zod";

import { createRecorder } from "../../src/record/recorder.js";
import { recordModel } from "../../src/record/model.js";
import { recordTools } from "../../src/record/tools.js";
import type { LedgerEvent } from "../../src/ledger/index.js";
import {
  ReplayDriftError,
  ReplayFixtureExhaustedError,
  ReplayUnconsumedError,
  assertReplayable,
  loadReplayFixture,
  replayModel,
} from "../../src/replay/index.js";

const PROMPT = "Can order 123 be refunded?";
const FINAL_TEXT = "Order 123 cannot be refunded.";

const toolCallResponse: LanguageModelV3GenerateResult = {
  content: [
    { type: "tool-call", toolCallId: "call-1", toolName: "lookupOrder", input: JSON.stringify({ orderId: "123" }) },
  ],
  finishReason: { unified: "tool-calls", raw: "tool_calls" },
  usage: {
    inputTokens: { total: 10, noCache: undefined, cacheRead: undefined, cacheWrite: undefined },
    outputTokens: { total: 5, text: undefined, reasoning: undefined },
  },
  warnings: [],
};

const finalResponse: LanguageModelV3GenerateResult = {
  content: [{ type: "text", text: FINAL_TEXT }],
  finishReason: { unified: "stop", raw: "stop" },
  usage: {
    inputTokens: { total: 20, noCache: undefined, cacheRead: undefined, cacheWrite: undefined },
    outputTokens: { total: 8, text: undefined, reasoning: undefined },
  },
  warnings: [],
};

function scriptedModel(responses: LanguageModelV3GenerateResult[]): MockLanguageModelV3 {
  let call = 0;
  return new MockLanguageModelV3({
    doGenerate: async () => {
      const response = responses[call++];
      if (!response) throw new Error(`scripted model exhausted after ${responses.length} calls`);
      return response;
    },
  });
}

type AgentConfig = {
  instructions?: string;
  toolDescription?: string;
  withForceParam?: boolean;
  lookupResult?: Record<string, unknown>;
};

function buildAgent(model: LanguageModelV3, config: AgentConfig = {}) {
  const schema = config.withForceParam
    ? z.object({ orderId: z.string(), force: z.boolean().optional() })
    : z.object({ orderId: z.string() });
  return new ToolLoopAgent({
    model,
    instructions: config.instructions ?? "Resolve refunds.",
    tools: {
      lookupOrder: tool({
        description: config.toolDescription ?? "Look up an order",
        inputSchema: schema,
        execute: async ({ orderId }: { orderId: string }) => config.lookupResult ?? { orderId, refundable: false },
      }),
    },
    stopWhen: stepCountIs(5),
  });
}

async function recordFixture(): Promise<LedgerEvent[]> {
  const recorder = createRecorder({ deterministic: true });
  const agent = buildAgent(recordModel(scriptedModel([toolCallResponse, finalResponse]), recorder));
  await recorder.run(PROMPT, () => agent.generate({ prompt: PROMPT }), { agentName: "support" });
  const { events } = await recorder.close();
  return events;
}

describe("replay through a real ToolLoopAgent (flagship loop)", () => {
  it("replays the recorded run keylessly and reproduces the trajectory", async () => {
    const fixtureEvents = await recordFixture();

    const { text, drift } = await assertReplayable(fixtureEvents, {
      agent: (model) => buildAgent(model),
    });

    expect(text).toBe(FINAL_TEXT);
    expect(drift).toEqual([]);
  });

  it("fails with a named drift when the instructions change", async () => {
    const fixtureEvents = await recordFixture();

    const error = await assertReplayable(fixtureEvents, {
      agent: (model) => buildAgent(model, { instructions: "Resolve refunds politely." }),
    }).then(
      () => undefined,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ReplayDriftError);
    const drift = error as ReplayDriftError;
    expect(drift.step).toBe(1);
    expect(drift.message).toContain("Replay drift at model call #1");
    expect(drift.message).toContain("prompt[0] (system): text differs");
    expect(drift.message).toContain("Resolve refunds.");
    expect(drift.message).toContain("Resolve refunds politely.");
    expect(drift.message).toContain("re-record the fixture");
  });

  it("fails with a named drift when a tool description changes", async () => {
    const fixtureEvents = await recordFixture();

    await expect(
      assertReplayable(fixtureEvents, {
        agent: (model) => buildAgent(model, { toolDescription: "Look up an order by id" }),
      }),
    ).rejects.toThrow(/tools\[lookupOrder\]: description differs/);
  });

  it("fails with a named drift when a tool input schema changes", async () => {
    const fixtureEvents = await recordFixture();

    await expect(
      assertReplayable(fixtureEvents, {
        agent: (model) => buildAgent(model, { withForceParam: true }),
      }),
    ).rejects.toThrow(/tools\[lookupOrder\]: inputSchema differs/);
  });

  it("fails with a drift when a tool's current output differs from the recording", async () => {
    const fixtureEvents = await recordFixture();

    // the changed tool result alters the step-2 request hash
    const error = await assertReplayable(fixtureEvents, {
      agent: (model) => buildAgent(model, { lookupResult: { orderId: "123", refundable: true } }),
    }).then(
      () => undefined,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ReplayDriftError);
    expect((error as ReplayDriftError).step).toBe(2);
    expect((error as ReplayDriftError).message).toContain("tool-result");
  });

  it("loose mode tolerates drift but reports it", async () => {
    const fixtureEvents = await recordFixture();

    const { text, drift } = await assertReplayable(fixtureEvents, {
      agent: (model) => buildAgent(model, { instructions: "Resolve refunds politely." }),
      mode: "loose",
    });

    expect(text).toBe(FINAL_TEXT);
    expect(drift).toHaveLength(2); // step 1 prompt drift cascades into step 2
    expect(drift[0].differences.join("\n")).toContain("prompt[0] (system): text differs");
  });

  it("throws ReplayFixtureExhaustedError when the loop grows a step", async () => {
    const fixtureEvents = await recordFixture();
    const fixture = await loadReplayFixture(fixtureEvents);
    // keep only the first recorded call: the agent will ask for a second
    const truncated = { ...fixture, modelCalls: fixture.modelCalls.slice(0, 1) };

    await expect(
      assertReplayable(truncated, {
        agent: (model) => buildAgent(model),
        compareOutput: false,
      }),
    ).rejects.toThrow(ReplayFixtureExhaustedError);
  });

  it("throws ReplayUnconsumedError when the loop shortens", async () => {
    const fixtureEvents = await recordFixture();

    await expect(
      assertReplayable(fixtureEvents, {
        agent: (model) =>
          new ToolLoopAgent({
            model,
            instructions: "Resolve refunds.",
            tools: {
              lookupOrder: tool({
                description: "Look up an order",
                inputSchema: z.object({ orderId: z.string() }),
                execute: async ({ orderId }: { orderId: string }) => ({ orderId, refundable: false }),
              }),
            },
            // a tightened stop condition ends the run after the first model
            // call, leaving the recorded final response unconsumed
            stopWhen: stepCountIs(1),
          }),
        mode: "loose",
        compareOutput: false,
      }),
    ).rejects.toThrow(ReplayUnconsumedError);
  });

  it("replays through agent.stream() with synthesized chunks", async () => {
    const fixtureEvents = await recordFixture();
    const fixture = await loadReplayFixture(fixtureEvents);
    const model = replayModel(fixture, { mode: "strict" });
    const agent = buildAgent(model);

    const result = await agent.stream({ prompt: PROMPT });
    let streamed = "";
    for await (const chunk of result.textStream) {
      streamed += chunk;
    }

    expect(streamed).toBe(FINAL_TEXT);
    model.assertExhausted();
  });

  it("supports event-level comparison via a caller-supplied recorder", async () => {
    const fixtureEvents = await recordFixture();

    const replayRecorder = createRecorder({ deterministic: true });
    await assertReplayable(fixtureEvents, {
      agent: (model) =>
        new ToolLoopAgent({
          model,
          instructions: "Resolve refunds.",
          tools: recordTools(
            {
              lookupOrder: tool({
                description: "Look up an order",
                inputSchema: z.object({ orderId: z.string() }),
                execute: async ({ orderId }: { orderId: string }) => ({ orderId, refundable: false }),
              }),
            },
            replayRecorder,
            { risk: { lookupOrder: "read" } },
          ),
          stopWhen: stepCountIs(5),
        }),
      recorder: replayRecorder,
    });

    // the replayed run produced its own full ledger
    const types = replayRecorder.events().map((event) => event.type);
    expect(types).toContain("tool.called");
    expect(types).toContain("model.completed");
  });

  it("strict mode refuses fixtures without request hashes", async () => {
    const fixtureEvents = await recordFixture();
    const fixture = await loadReplayFixture(fixtureEvents);
    const withoutHashes = {
      ...fixture,
      modelCalls: fixture.modelCalls.map((call) => ({ ...call, request: undefined })),
    };

    expect(() => replayModel(withoutHashes)).toThrow(/Strict replay requires recorded request hashes/);
    expect(() => replayModel(withoutHashes, { mode: "loose" })).not.toThrow();
  });
});
