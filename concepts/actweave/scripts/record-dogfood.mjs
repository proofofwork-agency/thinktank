// Records the dogfood fixture with a real provider, once, locally.
//
// Prereqs:
//   npm run build                 (imports the built dist/)
//   npm i -D @ai-sdk/openai-compatible   (or adapt the provider below)
//   OPENAI_COMPAT_BASE_URL  e.g. https://openrouter.ai/api/v1
//   OPENAI_COMPAT_API_KEY   provider key (never written to the fixture)
//   OPENAI_COMPAT_MODEL     e.g. google/gemini-2.5-flash
//
// Usage:
//   node scripts/record-dogfood.mjs
//
// Output: test/fixtures/dogfood/refund-denied.jsonl (review the diff, commit it).
// CI replays it keylessly via test/integration/dogfood-replay.test.ts.

import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { z } from "zod";
import { createRecorder, recordModel, recordTools } from "../dist/record/index.js";
import { writeGoldenLedgerSync } from "../dist/ledger/golden.js";

const baseURL = process.env.OPENAI_COMPAT_BASE_URL;
const apiKey = process.env.OPENAI_COMPAT_API_KEY;
const modelId = process.env.OPENAI_COMPAT_MODEL;

if (!baseURL || !apiKey || !modelId) {
  console.error("Set OPENAI_COMPAT_BASE_URL, OPENAI_COMPAT_API_KEY, OPENAI_COMPAT_MODEL.");
  process.exit(1);
}

let createOpenAICompatible;
try {
  ({ createOpenAICompatible } = await import("@ai-sdk/openai-compatible"));
} catch {
  console.error("Install the provider first: npm i -D @ai-sdk/openai-compatible");
  process.exit(1);
}

const provider = createOpenAICompatible({ name: "dogfood", baseURL, apiKey });

export const lookupOrder = tool({
  description: "Look up an order by ID.",
  inputSchema: z.object({ orderId: z.string() }),
  execute: async ({ orderId }) => ({
    orderId,
    status: orderId === "123" ? "expired" : "open",
    refundable: orderId !== "123",
    amount: orderId === "123" ? 49.99 : 12.5,
  }),
});

const recorder = createRecorder({ deterministic: true });

const agent = new ToolLoopAgent({
  model: recordModel(provider(modelId), recorder),
  instructions:
    "Resolve refund requests. If the user provides an order ID, call lookupOrder with that ID before answering. Never refund expired orders.",
  tools: recordTools({ lookupOrder }, recorder, { risk: { lookupOrder: "read" } }),
  stopWhen: stepCountIs(5),
  temperature: 0,
});

const input = "Can order ID 123 be refunded? Use lookupOrder to check order 123 first.";
const result = await recorder.run(input, () => agent.generate({ prompt: input }), { agentName: "support" });
const { events, summary } = await recorder.close();

writeGoldenLedgerSync("test/fixtures/dogfood/refund-denied.jsonl", events, {
  meta: { scenario: "refund-denied", provider: "openai-compatible", modelId },
});

console.log(`Recorded ${summary.eventCount} events (${summary.calls.length} calls).`);
console.log(`Final answer: ${result.text}`);
console.log("Wrote test/fixtures/dogfood/refund-denied.jsonl — review the diff and commit it.");
