import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { afterEach, describe, expect, it } from "vitest";

import { createRecorder } from "../src/record/recorder.js";
import { readGoldenLedgerSync, writeGoldenLedgerSync } from "../src/ledger/golden.js";
import { JsonlLedgerWriter, canonicalEventLine, parseJsonlLedger } from "../src/ledger/index.js";

describe("deterministic recording", () => {
  let tempDirs: string[] = [];

  afterEach(async () => {
    await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })));
    tempDirs = [];
  });

  async function tempDir(): Promise<string> {
    const dir = await mkdtemp(join(tmpdir(), "actweave-golden-"));
    tempDirs.push(dir);
    return dir;
  }

  async function recordSampleRun(): Promise<string[]> {
    const recorder = createRecorder({ deterministic: true });
    await recorder.run(
      "Can order 123 be refunded?",
      async () => {
        const step = recorder.beginModelStep();
        await recorder.modelCalled(step, undefined, undefined, {
          hash: "sha256:abc",
          prompt: [{ role: "user", content: "Can order 123 be refunded?" }],
        });
        await recorder.modelCompleted(step, {
          content: [{ type: "tool-call", toolCallId: "call-1", toolName: "lookupOrder", input: { orderId: "123" } }],
          finishReason: "tool-calls",
          usage: { inputTokens: 10, outputTokens: 5, totalTokens: 15 },
          provider: "test",
        });
        await recorder.toolCalled(
          recorder.currentStep(),
          "lookupOrder",
          { orderId: "123" },
          "read",
          undefined,
          "call-1",
        );
        await recorder.toolCompleted(recorder.currentStep(), "lookupOrder", { refundable: false }, undefined, "call-1");
        const finalStep = recorder.beginModelStep();
        await recorder.modelCalled(finalStep, undefined, undefined, { hash: "sha256:def" });
        await recorder.modelCompleted(finalStep, {
          content: [{ type: "text", text: "Order 123 cannot be refunded." }],
          finishReason: "stop",
          provider: "test",
        });
        return { text: "Order 123 cannot be refunded." };
      },
      { agentName: "support" },
    );
    const { events } = await recorder.close();
    return events.map((event) => canonicalEventLine(event));
  }

  it("produces byte-identical lines across two identical recordings", async () => {
    const first = await recordSampleRun();
    const second = await recordSampleRun();
    expect(first.length).toBeGreaterThan(0);
    expect(second).toEqual(first);
  });

  it("uses sequence ids and a fixed epoch clock", async () => {
    const lines = await recordSampleRun();
    const events = parseJsonlLedger(lines.join("\n"));
    expect(events.ok).toBe(true);
    expect(events.events[0]?.id).toBe("evt-1");
    expect(events.events[0]?.runId).toBe("run");
    expect(events.events[0]?.timestamp).toBe("2020-01-01T00:00:00.000Z");
    expect(events.events[1]?.timestamp).toBe("2020-01-01T00:00:00.001Z");
  });

  it("records the model text as model.completed output and the run output from .text", async () => {
    const lines = await recordSampleRun();
    const events = parseJsonlLedger(lines.join("\n")).events;
    const completions = events.filter((event) => event.type === "model.completed");
    expect(completions.at(-1)?.output).toBe("Order 123 cannot be refunded.");
    expect(events.find((event) => event.type === "run.completed")?.output).toBe("Order 123 cannot be refunded.");
  });

  it("JsonlLedgerWriter writes canonical lines identical to golden serialization", async () => {
    const dir = await tempDir();
    const path = join(dir, "run.jsonl");
    const writer = await JsonlLedgerWriter.open(path, { deterministic: true });
    await writer.append({ type: "run.started", input: "hello" });
    await writer.append({ type: "run.completed", output: "done" });
    await writer.close();

    const content = await readFile(path, "utf8");
    const expected = writer
      .events()
      .map((event) => canonicalEventLine(event))
      .join("\n");
    expect(content.trim()).toBe(expected);
  });
});

describe("golden fixtures", () => {
  let tempDirs: string[] = [];

  afterEach(async () => {
    await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })));
    tempDirs = [];
  });

  async function tempDir(): Promise<string> {
    const dir = await mkdtemp(join(tmpdir(), "actweave-golden-"));
    tempDirs.push(dir);
    return dir;
  }

  it("writes a meta line plus canonical events and reads them back", async () => {
    const dir = await tempDir();
    const path = join(dir, "fixture.jsonl");

    const recorder = createRecorder({ deterministic: true });
    await recorder.runStarted("hi", "support");
    await recorder.runCompleted("done");
    const { events } = await recorder.close();

    writeGoldenLedgerSync(path, events, {
      meta: { provider: "test-provider", modelId: "test-model", scenario: "smoke" },
    });

    const content = await readFile(path, "utf8");
    const lines = content.trim().split("\n");
    expect(lines).toHaveLength(3);
    expect(JSON.parse(lines[0])).toEqual({
      __golden_meta: true,
      schema: "actweave.golden.v2",
      provider: "test-provider",
      modelId: "test-model",
      scenario: "smoke",
    });

    const golden = readGoldenLedgerSync(path);
    expect(golden.meta?.schema).toBe("actweave.golden.v2");
    expect(golden.meta?.recordedAt).toBeUndefined();
    expect(golden.validation.ok).toBe(true);
    expect(golden.events.map((event) => event.type)).toEqual(["run.started", "run.completed"]);
  });

  it("re-writing the same events produces a byte-identical file", async () => {
    const dir = await tempDir();
    const path = join(dir, "fixture.jsonl");

    const recorder = createRecorder({ deterministic: true });
    await recorder.runStarted("hi");
    await recorder.runCompleted("done");
    const { events } = await recorder.close();

    writeGoldenLedgerSync(path, events, { meta: { scenario: "stable" } });
    const first = await readFile(path, "utf8");
    writeGoldenLedgerSync(path, events, { meta: { scenario: "stable" } });
    const second = await readFile(path, "utf8");
    expect(second).toBe(first);
  });

  it("orders keys canonically regardless of event object key order", () => {
    const recorder = createRecorder({ deterministic: true });
    const line = canonicalEventLine({
      // intentionally scrambled creation order
      type: "run.started",
      seq: 1,
      id: "evt-1",
      timestamp: "2020-01-01T00:00:00.000Z",
      traceId: "run",
      runId: "run",
      schemaVersion: "actweave.ledger.v2",
    });
    expect(line.startsWith('{"schemaVersion":"actweave.ledger.v2","id":"evt-1","runId":"run","traceId":"run"')).toBe(
      true,
    );
    expect(recorder.runId).toBe("run");
  });

  it("rejects actweave.ledger.v1 fixtures with a re-record message", () => {
    const v1Line = JSON.stringify({
      schemaVersion: "actweave.ledger.v1",
      id: "old-1",
      runId: "run-old",
      traceId: "trace-old",
      seq: 1,
      timestamp: "2026-06-08T16:55:49.243Z",
      type: "run.started",
    });

    const parsed = parseJsonlLedger(v1Line);
    expect(parsed.ok).toBe(false);
    expect(parsed.issues.map((issue) => issue.message)).toContain(
      "actweave.ledger.v1 fixtures are not supported; re-record with actweave v2",
    );
  });

  it("records run.failed through the run() helper and rethrows", async () => {
    const recorder = createRecorder({ deterministic: true });
    await expect(
      recorder.run("boom", () => {
        throw new Error("tool exploded");
      }),
    ).rejects.toThrow("tool exploded");

    const events = recorder.events();
    expect(events.map((event) => event.type)).toEqual(["run.started", "run.failed"]);
    expect(events.at(-1)?.error?.message).toBe("tool exploded");
  });
});
