import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { isRecord } from "../internal/guards.js";
import { canonicalEventLine, parseJsonlLedger, type LedgerEvent, type LedgerValidationResult } from "./index.js";

export const GOLDEN_SCHEMA_VERSION = "actweave.golden.v2" as const;

export type GoldenMeta = {
  schema: typeof GOLDEN_SCHEMA_VERSION;
  recordedWith?: {
    ai?: string;
    actweave?: string;
  };
  provider?: string;
  modelId?: string;
  scenario?: string;
  recordedAt?: string;
};

export type GoldenLedger = {
  meta?: GoldenMeta;
  validation: LedgerValidationResult;
  events: LedgerEvent[];
};

export type WriteGoldenOptions = {
  meta?: Omit<GoldenMeta, "schema">;
  /**
   * Stamp a recordedAt timestamp into the meta line. Off by default so an
   * unchanged re-record produces a zero-line git diff.
   */
  includeTimestamp?: boolean | (() => Date);
};

export function writeGoldenLedgerSync(
  path: string,
  events: readonly LedgerEvent[],
  options: WriteGoldenOptions = {},
): void {
  mkdirSync(dirname(path), { recursive: true });
  const meta: GoldenMeta = {
    schema: GOLDEN_SCHEMA_VERSION,
    ...options.meta,
  };
  if (options.includeTimestamp) {
    const now = typeof options.includeTimestamp === "function" ? options.includeTimestamp() : new Date();
    meta.recordedAt = now.toISOString();
  }
  const lines = [JSON.stringify({ __golden_meta: true, ...meta })];
  for (const event of events) {
    lines.push(canonicalEventLine(event));
  }
  writeFileSync(path, `${lines.join("\n")}\n`, "utf8");
}

export function readGoldenLedgerSync(path: string): GoldenLedger {
  const content = readFileSync(path, "utf8");
  const meta = extractGoldenMeta(content);
  const validation = parseJsonlLedger(content);
  return {
    ...(meta ? { meta } : {}),
    validation,
    events: validation.events,
  };
}

function extractGoldenMeta(content: string): GoldenMeta | undefined {
  for (const line of content.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    if (!line.trim()) {
      continue;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      return undefined;
    }
    if (isRecord(parsed) && parsed.__golden_meta === true) {
      const { __golden_meta: _marker, ...rest } = parsed;
      return rest as GoldenMeta;
    }
    return undefined;
  }
  return undefined;
}
