// Records the fixture this example replays in its tests.
//
// By default it records from a scripted model so the whole example runs
// WITHOUT any API key — the recording still flows through the real
// ToolLoopAgent, real tool execution, and the real Actweave recorder.
//
// To record from a live provider instead, swap the model construction at the
// bottom (any LanguageModelV3 works), e.g.:
//
//   import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
//   const provider = createOpenAICompatible({ name: "demo", baseURL, apiKey });
//   const model = provider("google/gemini-2.5-flash");

import { MockLanguageModelV3 } from "ai/test";
import { createRecorder, recordModel, recordTools } from "actweave/record";
import { writeGoldenLedgerSync } from "actweave/ledger";
import { INPUT, buildSupportAgent, lookupOrder } from "../src/agent.mjs";

const scripted = [
  {
    content: [
      { type: "tool-call", toolCallId: "call-1", toolName: "lookupOrder", input: JSON.stringify({ orderId: "123" }) },
    ],
    finishReason: { unified: "tool-calls", raw: "tool_calls" },
    usage: {
      inputTokens: { total: 85, noCache: undefined, cacheRead: undefined, cacheWrite: undefined },
      outputTokens: { total: 7, text: undefined, reasoning: undefined },
    },
    warnings: [],
  },
  {
    content: [{ type: "text", text: "Order 123 has expired and cannot be refunded." }],
    finishReason: { unified: "stop", raw: "stop" },
    usage: {
      inputTokens: { total: 132, noCache: undefined, cacheRead: undefined, cacheWrite: undefined },
      outputTokens: { total: 11, text: undefined, reasoning: undefined },
    },
    warnings: [],
  },
];

let call = 0;
const model = new MockLanguageModelV3({ doGenerate: async () => scripted[call++] });

const recorder = createRecorder({ deterministic: true });
const agent = buildSupportAgent(recordModel(model, recorder), {
  tools: recordTools({ lookupOrder }, recorder, { risk: { lookupOrder: "read" } }),
});

const result = await recorder.run(INPUT, () => agent.generate({ prompt: INPUT }), { agentName: "support" });
const { events, summary } = await recorder.close();

writeGoldenLedgerSync("fixtures/refund-denied.jsonl", events, {
  meta: { scenario: "refund-denied", provider: "scripted-demo", modelId: "mock-model-id" },
});

console.log(`Recorded ${summary.eventCount} events. Final answer: ${result.text}`);
console.log("Wrote fixtures/refund-denied.jsonl");
