import { describe, expect, it } from "vitest";
import { createRecorder } from "../src/record/recorder.js";
import { compareRuns } from "../src/replay/compare.js";
import type { LedgerEvent } from "../src/ledger/index.js";

async function runWithToolOutput(output: Record<string, unknown>, runOutput = "done"): Promise<LedgerEvent[]> {
  const recorder = createRecorder({ deterministic: true });
  await recorder.runStarted("hi", "support");
  await recorder.toolCalled(1, "fetchUser", { id: "u1" }, "read", undefined, "call-1");
  await recorder.toolCompleted(1, "fetchUser", output, undefined, "call-1");
  await recorder.runCompleted(runOutput);
  return [...(await recorder.close()).events];
}

describe("compareRuns", () => {
  it("passes for identical runs", async () => {
    const expected = await runWithToolOutput({ id: "u1", name: "Dana" });
    const actual = await runWithToolOutput({ id: "u1", name: "Dana" });
    expect(compareRuns(expected, actual).pass).toBe(true);
  });

  it("fails on differing tool outputs by default", async () => {
    const expected = await runWithToolOutput({ id: "u1", fetchedAt: "2026-01-01T00:00:00Z" });
    const actual = await runWithToolOutput({ id: "u1", fetchedAt: "2026-06-10T12:00:00Z" });
    const diff = compareRuns(expected, actual);
    expect(diff.pass).toBe(false);
    expect(diff.toolOutputs.pass).toBe(false);
  });

  it("ignorePaths prunes volatile fields on both sides", async () => {
    const expected = await runWithToolOutput({ id: "u1", fetchedAt: "2026-01-01T00:00:00Z" });
    const actual = await runWithToolOutput({ id: "u1", fetchedAt: "2026-06-10T12:00:00Z" });
    expect(compareRuns(expected, actual, { ignorePaths: ["fetchedAt"] }).pass).toBe(true);
  });

  it("ignorePaths supports wildcards into arrays", async () => {
    const expected = await runWithToolOutput({
      items: [
        { sku: "a", ts: 1 },
        { sku: "b", ts: 2 },
      ],
    });
    const actual = await runWithToolOutput({
      items: [
        { sku: "a", ts: 9 },
        { sku: "b", ts: 8 },
      ],
    });
    expect(compareRuns(expected, actual).pass).toBe(false);
    expect(compareRuns(expected, actual, { ignorePaths: ["items[*].ts"] }).pass).toBe(true);
  });

  it("normalizers can rewrite outputs before comparison", async () => {
    const expected = await runWithToolOutput({ id: "u1" }, "Processed 3 records at 10:00");
    const actual = await runWithToolOutput({ id: "u1" }, "Processed 3 records at 11:30");
    const diff = compareRuns(expected, actual, {
      normalizers: {
        runOutput: (output) => (typeof output === "string" ? output.replace(/at \d+:\d+/, "at <time>") : output),
      },
    });
    expect(diff.pass).toBe(true);
  });

  it("flags side-effectful calls unless allowed", async () => {
    const recorder = createRecorder({ deterministic: true });
    await recorder.runStarted("hi");
    await recorder.toolCalled(1, "sendEmail", { to: "x@y.z" }, "network", undefined, "call-1");
    await recorder.toolCompleted(1, "sendEmail", { sent: true }, undefined, "call-1");
    await recorder.runCompleted("done");
    const events = [...(await recorder.close()).events];

    expect(compareRuns(events, events).pass).toBe(false);
    expect(compareRuns(events, events, { allowSideEffects: true }).pass).toBe(true);
  });
});
