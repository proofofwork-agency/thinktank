import { describe, expect, it } from "vitest";
import { check } from "actweave";
import { assertReplayable, ReplayDriftError } from "actweave/replay";
import { readGoldenLedgerSync } from "actweave/ledger";
import { extendActweaveMatchers } from "actweave/vitest";
// @ts-expect-error plain-JS example module
import { buildSupportAgent } from "../src/agent.mjs";

extendActweaveMatchers(expect);

const FIXTURE = "fixtures/refund-denied.jsonl";

describe("refund agent (replayed keylessly from the committed fixture)", () => {
  it("replays the recorded path through the real agent", async () => {
    const { text } = await assertReplayable(FIXTURE, {
      agent: (model) => buildSupportAgent(model),
    });
    expect(text).toBe("Order 123 has expired and cannot be refunded.");
  });

  it("asserts the recorded trajectory", () => {
    const { events } = readGoldenLedgerSync(FIXTURE);
    check(events)
      .completed()
      .noErrors()
      .called("lookupOrder")
      .calledWith("lookupOrder", { orderId: "123" })
      .notCalled("issueRefund")
      .outputMatches(/cannot be refunded/i)
      .validLifecycle();
    expect(events).toHaveCalledTool("lookupOrder", { orderId: "123" });
  });

  it("fails with a named drift when the prompt changes (this is the point)", async () => {
    const error = await assertReplayable(FIXTURE, {
      agent: (model) => buildSupportAgent(model, { instructions: "Resolve refunds. Always offer a coupon." }),
    }).then(
      () => undefined,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ReplayDriftError);
    expect((error as Error).message).toContain("prompt[0] (system): text differs");
  });
});
