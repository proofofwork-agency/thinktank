import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { afterEach, describe, expect, it } from "vitest";

import { check } from "../src/check/index.js";
import { resultToLedgerEvents } from "../src/check/result.js";
import { createRecorder } from "../src/record/recorder.js";
import { actweaveMatchers, extendActweaveMatchers } from "../src/vitest.js";
import type { LedgerEvent } from "../src/ledger/index.js";

extendActweaveMatchers(expect);

async function sampleRun(): Promise<LedgerEvent[]> {
  const recorder = createRecorder({ deterministic: true });
  await recorder.runStarted("Can order 123 be refunded?", "support");
  await recorder.toolCalled(1, "lookupOrder", { orderId: "123" }, "read", undefined, "call-1");
  await recorder.toolCompleted(1, "lookupOrder", { refundable: false }, undefined, "call-1");
  await recorder.runCompleted("Order 123 cannot be refunded because it expired.");
  return [...(await recorder.close()).events];
}

describe("unified check()", () => {
  it("accepts event arrays, recorders, and AI SDK results", async () => {
    const events = await sampleRun();
    check(events).completed().called("lookupOrder");

    const recorder = createRecorder({ deterministic: true });
    await recorder.runStarted("hi");
    await recorder.runCompleted("done");
    check(recorder).completed();

    const aiResult = {
      text: "Order 123 cannot be refunded.",
      steps: [
        {
          text: "",
          finishReason: "tool-calls",
          toolCalls: [{ toolCallId: "call-1", toolName: "lookupOrder", input: { orderId: "123" } }],
          toolResults: [{ toolCallId: "call-1", toolName: "lookupOrder", output: { refundable: false } }],
        },
        { text: "Order 123 cannot be refunded.", finishReason: "stop", toolCalls: [], toolResults: [] },
      ],
    };
    check(aiResult).completed().called("lookupOrder").calledWith("lookupOrder", { orderId: "123" });
  });

  it("outputContains and outputMatches assert on the run output", async () => {
    const events = await sampleRun();
    check(events)
      .outputContains("expired")
      .outputMatches(/cannot be refunded/i);
    expect(() => check(events).outputContains("refund approved")).toThrow(/expected run output to contain/);
  });

  it("durationBelow measures recorded timestamps", async () => {
    const events = await sampleRun();
    check(events).durationBelow(1000);
    expect(() => check(events).durationBelow(0)).toThrow(/expected run duration below 0ms/);
  });

  it("resultToLedgerEvents marks derived events and validates", async () => {
    const events = resultToLedgerEvents(
      { text: "done", steps: [{ text: "done", finishReason: "stop", toolCalls: [], toolResults: [] }] },
      { agentName: "support", input: "hi" },
    );
    expect(events[0].metadata?.derivedFrom).toBe("ai-sdk-result");
    check(events).completed().validLifecycle();
  });
});

describe("golden matching", () => {
  let tempDirs: string[] = [];

  afterEach(async () => {
    await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })));
    tempDirs = [];
  });

  it("writes on first run, matches on subsequent runs, fails on drift", async () => {
    const dir = await mkdtemp(join(tmpdir(), "actweave-check-"));
    tempDirs.push(dir);
    const path = join(dir, "golden.jsonl");

    const events = await sampleRun();
    check(events).toMatchGolden(path); // writes
    check(events).toMatchGolden(path); // matches

    const recorder = createRecorder({ deterministic: true });
    await recorder.runStarted("Can order 123 be refunded?", "support");
    await recorder.toolCalled(1, "lookupOrder", { orderId: "999" }, "read", undefined, "call-1");
    await recorder.toolCompleted(1, "lookupOrder", { refundable: false }, undefined, "call-1");
    await recorder.runCompleted("Order 123 cannot be refunded because it expired.");
    const drifted = [...(await recorder.close()).events];

    expect(() => check(drifted).toMatchGolden(path)).toThrow(/does not match golden fixture/);
  });
});

describe("vitest matchers", () => {
  it("expose pass/fail through expect.extend", async () => {
    const events = await sampleRun();
    expect(events).toBeCompletedRun();
    expect(events).toHaveCalledTool("lookupOrder", { orderId: "123" });
    expect(events).toHaveNoErrors();
    expect(events).toHaveValidLifecycle();
    expect(events).toHaveEventSequence(["run.started", "tool.called", "tool.completed", "run.completed"]);

    const failing = actweaveMatchers.toHaveCalledTool(events, "issueRefund");
    expect(failing.pass).toBe(false);
    expect(failing.message()).toContain('expected tool "issueRefund" to be called');
  });
});
