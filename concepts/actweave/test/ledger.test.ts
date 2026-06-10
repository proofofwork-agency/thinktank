import { mkdtemp, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { describe, expect, it } from "vitest";

import {
  InMemoryLedger,
  JsonlLedgerWriter,
  buildLedgerSummary,
  parseJsonlLedger,
  readJsonlLedger,
  validateLedgerEvent,
  validateLedgerLifecycle,
  writeLedgerSummary,
} from "../src/ledger/index.js";

describe("ledger", () => {
  it("writes append-safe JSONL events and reads them back", async () => {
    const dir = await mkdtemp(join(tmpdir(), "actweave-ledger-"));
    try {
      const path = join(dir, "run.jsonl");
      const writer = await JsonlLedgerWriter.open(path, {
        runId: "run-1",
        traceId: "trace-1",
        now: fixedClock(),
        ids: sequenceIds("evt"),
      });

      await writer.append({ type: "run.started", input: { prompt: "hello" } });
      await writer.append({
        type: "tool.completed",
        callId: "call-1",
        name: "lookupOrder",
        replay: { kind: "tool", sideEffect: false },
        input: { orderId: "123" },
        output: { eligible: false },
      });
      await writer.close();

      const content = await readFile(path, "utf8");
      expect(content.trim().split("\n")).toHaveLength(2);

      const read = await readJsonlLedger(path);
      expect(read.ok).toBe(true);
      expect(read.events.map((event) => event.seq)).toEqual([1, 2]);
      expect(read.events.map((event) => event.runId)).toEqual(["run-1", "run-1"]);
      expect(buildLedgerSummary(read.events).eventCount).toBe(2);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("keeps an in-memory ledger and builds a summary fixture", async () => {
    const ledger = new InMemoryLedger({
      runId: "run-memory",
      traceId: "trace-memory",
      now: fixedClock(),
      ids: sequenceIds("mem"),
    });

    await ledger.append({ type: "run.started", input: { prompt: "refund?" } });
    await ledger.append({
      type: "model.completed",
      callId: "model-1",
      name: "gpt-test",
      replay: { kind: "model" },
      output: { text: "No refund." },
    });
    await ledger.append({ type: "run.completed", output: { text: "No refund." } });

    const summary = ledger.summary();
    expect(summary.schemaVersion).toBe("actweave.summary.v2");
    expect(summary.runId).toBe("run-memory");
    expect(summary.eventCount).toBe(3);
    expect(summary.eventTypes).toEqual({
      "model.completed": 1,
      "run.completed": 1,
      "run.started": 1,
    });
    expect(summary.calls).toEqual([
      expect.objectContaining({
        callId: "model-1",
        kind: "model",
        name: "gpt-test",
      }),
    ]);
  });

  it("redacts secret keys and authorization token strings", async () => {
    const ledger = new InMemoryLedger({
      runId: "run-redact",
      traceId: "trace-redact",
      now: fixedClock(),
      ids: sequenceIds("redact"),
    });

    const event = await ledger.append({
      type: "tool.started",
      input: {
        headers: {
          Authorization: "Bearer abcdefghijklmnopqrstuvwxyz",
          "x-api-key": "plain-secret",
        },
        nested: {
          token: "token-value",
        },
        message: "use sk-abcdefghijklmnopqrstuvwxyz carefully",
      },
    });

    expect(event.input).toEqual({
      headers: {
        Authorization: "[REDACTED]",
        "x-api-key": "[REDACTED]",
      },
      nested: {
        token: "[REDACTED]",
      },
      message: "[REDACTED]",
    });
    expect(event.redaction?.count).toBe(4);
    expect(event.redaction?.paths).toEqual([
      "input.headers.Authorization",
      "input.headers.x-api-key",
      "input.message",
      "input.nested.token",
    ]);
  });

  it("handles payload size limits with attachment references", async () => {
    const ledger = new InMemoryLedger({
      runId: "run-large",
      traceId: "trace-large",
      now: fixedClock(),
      ids: sequenceIds("large"),
      payloadLimit: {
        maxStringBytes: 8,
        maxEventBytes: 512,
      },
    });

    const event = await ledger.append({
      type: "tool.completed",
      output: {
        body: "this output is too large for inline storage",
      },
    });

    expect(event.output).toEqual({
      body: expect.objectContaining({
        __actweave: "truncated",
        bytes: 43,
        path: "output.body",
      }),
    });
    expect(event.attachments).toEqual([
      expect.objectContaining({
        bytes: 43,
        reason: "payload-limit",
      }),
    ]);
  });

  it("validates schema and event sequence", async () => {
    const valid = await new InMemoryLedger({
      runId: "run-valid",
      traceId: "trace-valid",
      now: fixedClock(),
      ids: sequenceIds("valid"),
    }).append({ type: "run.started" });

    expect(validateLedgerEvent(valid).ok).toBe(true);

    const parsed = parseJsonlLedger(
      [
        JSON.stringify(valid),
        JSON.stringify({
          ...valid,
          id: "different",
          seq: 1,
        }),
      ].join("\n"),
    );

    expect(parsed.ok).toBe(false);
    expect(parsed.issues.map((issue) => issue.path)).toContain("seq");
  });

  it("parses JSONL content with a UTF-8 BOM", async () => {
    const event = await new InMemoryLedger({
      runId: "run-bom",
      traceId: "trace-bom",
      now: fixedClock(),
      ids: sequenceIds("bom"),
    }).append({ type: "run.started" });

    const parsed = parseJsonlLedger(`\uFEFF${JSON.stringify(event)}\n`);

    expect(parsed.ok).toBe(true);
    expect(parsed.events).toHaveLength(1);
    expect(parsed.events[0]?.runId).toBe("run-bom");
  });

  it("validates lifecycle ordering only when requested", async () => {
    const ledger = new InMemoryLedger({
      runId: "run-lifecycle",
      traceId: "trace-lifecycle",
      now: fixedClock(),
      ids: sequenceIds("lifecycle"),
    });

    await ledger.append({ type: "run.started" });
    await ledger.append({
      type: "tool.completed",
      callId: "call-1",
      name: "lookupOrder",
      replay: { kind: "tool", sideEffect: false },
      output: { ok: true },
    });

    const lifecycle = validateLedgerLifecycle(ledger.events());

    expect(lifecycle.ok).toBe(false);
    expect(lifecycle.issues.map((issue) => issue.message)).toContain("tool.completed occurred before its start event");
  });

  it("allows multiple run ids inside one handoff trace ledger", async () => {
    const ledger = new InMemoryLedger({
      runId: "run-parent",
      traceId: "trace-handoff",
      now: fixedClock(),
      ids: sequenceIds("handoff"),
    });

    await ledger.append({ type: "run.started" });
    await ledger.append({
      type: "run.started",
      runId: "run-child",
      traceId: "trace-handoff",
      parentRunId: "run-parent",
    });

    const parsed = parseJsonlLedger(
      ledger
        .events()
        .map((event) => JSON.stringify(event))
        .join("\n"),
    );

    expect(parsed.ok).toBe(true);
    expect(parsed.events.map((event) => event.runId)).toEqual(["run-parent", "run-child"]);
  });

  it("writes and inspects a .actweave.json summary", async () => {
    const dir = await mkdtemp(join(tmpdir(), "actweave-summary-"));
    try {
      const ledger = new InMemoryLedger({
        runId: "run-summary",
        traceId: "trace-summary",
        now: fixedClock(),
        ids: sequenceIds("summary"),
      });
      await ledger.append({ type: "run.started" });
      await ledger.append({ type: "run.completed" });

      const summaryPath = join(dir, "run.actweave.json");
      const summary = await writeLedgerSummary(summaryPath, ledger.events());

      expect(summary).toEqual(buildLedgerSummary(ledger.events()));

      const written = JSON.parse(await readFile(summaryPath, "utf8")) as { eventCount: number };
      expect(written).toEqual(summary);
      expect(written.eventCount).toBe(2);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});

function fixedClock(): () => Date {
  return () => new Date("2026-06-07T12:00:00.000Z");
}

function sequenceIds(prefix: string): () => string {
  let index = 0;
  return () => `${prefix}-${++index}`;
}
