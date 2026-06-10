import { describe, expect, it } from "vitest";
import { ToolLoopAgent, stepCountIs, tool, wrapLanguageModel } from "ai";
import { MockLanguageModelV3 } from "ai/test";
import type { LanguageModelV3CallOptions, LanguageModelV3GenerateResult } from "@ai-sdk/provider";
import { z } from "zod";

/**
 * De-risking spike for the two load-bearing architectural assumptions:
 *  1. wrapLanguageModel middleware fires once per ToolLoopAgent loop step and
 *     sees both the request params and the response.
 *  2. params carry the full message-array prompt and tool definitions with
 *     inputSchema already converted to JSON Schema.
 * If this file fails after an `ai` upgrade, the recorder design must be
 * revisited before trusting any other integration test.
 */

const toolCallResponse: LanguageModelV3GenerateResult = {
  content: [
    {
      type: "tool-call",
      toolCallId: "call-1",
      toolName: "lookupOrder",
      input: JSON.stringify({ orderId: "123" }),
    },
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
  // Function form: MockLanguageModelV3's array form is off-by-one in
  // ai@6.0.199 (pushes the call before indexing by length).
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

describe("AI SDK integration spike", () => {
  it("middleware fires per loop step and sees prompt + JSON-schema tools", async () => {
    const captured: Array<{ params: LanguageModelV3CallOptions; result: LanguageModelV3GenerateResult }> = [];

    const agent = new ToolLoopAgent({
      model: wrapLanguageModel({
        model: scriptedModel([toolCallResponse, finalResponse]),
        middleware: {
          wrapGenerate: async ({ doGenerate, params }) => {
            const result = await doGenerate();
            captured.push({ params, result });
            return result;
          },
        },
      }),
      instructions: "Resolve refunds.",
      tools: {
        lookupOrder: tool({
          description: "Look up an order",
          inputSchema: z.object({ orderId: z.string() }),
          execute: async ({ orderId }) => ({ orderId, refundable: false }),
        }),
      },
      stopWhen: stepCountIs(5),
    });

    const result = await agent.generate({ prompt: "Can order 123 be refunded?" });

    // one middleware invocation per model call in the loop
    expect(captured).toHaveLength(2);

    // step 1: system + user prompt, tools with JSON Schema inputSchema
    const step1 = captured[0].params;
    expect(step1.prompt[0]).toMatchObject({ role: "system", content: "Resolve refunds." });
    expect(step1.prompt[1]).toMatchObject({ role: "user" });
    expect(step1.tools?.[0]).toMatchObject({
      type: "function",
      name: "lookupOrder",
      inputSchema: expect.objectContaining({ type: "object" }),
    });

    // step 2 prompt threads step 1's tool call and tool result
    const step2Tail = captured[1].params.prompt.slice(-2);
    expect(step2Tail[0]).toMatchObject({
      role: "assistant",
      content: [expect.objectContaining({ type: "tool-call", toolCallId: "call-1", toolName: "lookupOrder" })],
    });
    expect(step2Tail[1]).toMatchObject({
      role: "tool",
      content: [expect.objectContaining({ type: "tool-result", toolCallId: "call-1" })],
    });

    // loop result reflects both steps
    expect(result.steps).toHaveLength(2);
    expect(result.text).toBe("Order 123 cannot be refunded.");
    expect(result.steps[0].toolCalls.map((call) => call.toolName)).toEqual(["lookupOrder"]);
  });
});
