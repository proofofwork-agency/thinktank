import { existsSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { z } from "zod";

import { assertReplayable } from "../../src/replay/index.js";
import { check } from "../../src/check/index.js";
import { loadReplayFixture } from "../../src/replay/fixture.js";
import { readGoldenLedgerSync } from "../../src/ledger/golden.js";

const FIXTURE = "test/fixtures/dogfood/refund-denied.jsonl";

// Recorded once with a real provider via scripts/record-dogfood.mjs and
// committed; this suite replays it with NO API key. Skipped until the
// fixture has been recorded (human step — requires a provider key).
describe.skipIf(!existsSync(FIXTURE))("dogfood: real-provider fixture replays keylessly", () => {
  const lookupOrder = tool({
    description: "Look up an order by ID.",
    inputSchema: z.object({ orderId: z.string() }),
    execute: async ({ orderId }: { orderId: string }) => ({
      orderId,
      status: orderId === "123" ? "expired" : "open",
      refundable: orderId !== "123",
      amount: orderId === "123" ? 49.99 : 12.5,
    }),
  });

  it("replays strict with the recorded trajectory", async () => {
    const { text } = await assertReplayable(FIXTURE, {
      agent: (model) =>
        new ToolLoopAgent({
          model,
          instructions:
            "Resolve refund requests. If the user provides an order ID, call lookupOrder with that ID before answering. Never refund expired orders.",
          tools: { lookupOrder },
          stopWhen: stepCountIs(5),
        }),
    });
    expect(text).toBeTruthy();
  });

  it("asserts the recorded trajectory shape", async () => {
    const golden = readGoldenLedgerSync(FIXTURE);
    expect(golden.meta?.scenario).toBe("refund-denied");
    check(golden.events).completed().noErrors().called("lookupOrder").calledWith("lookupOrder", { orderId: "123" });

    const fixture = await loadReplayFixture(FIXTURE);
    expect(fixture.modelCalls.length).toBeGreaterThanOrEqual(2);
    for (const call of fixture.modelCalls) {
      expect(call.request?.hash).toMatch(/^sha256:/);
    }
  });
});
