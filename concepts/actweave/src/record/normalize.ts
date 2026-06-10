import { createHash } from "node:crypto";
import { isRecord } from "../internal/guards.js";
import { stableStringify } from "../internal/compare.js";
import type { JsonValue, LedgerModelRequest, LedgerModelRequestTool } from "../ledger/index.js";

/**
 * Sampling knobs that never enter the request hash. They are recorded under
 * request.settings for diff display, so a temperature tweak does not
 * invalidate fixtures while a prompt or tool change does.
 */
const SETTINGS_KEYS = [
  "temperature",
  "topP",
  "topK",
  "maxOutputTokens",
  "presencePenalty",
  "frequencyPenalty",
  "stopSequences",
  "seed",
] as const;

export type NormalizeRequestOptions = {
  /** Include sampling settings in the hash (off by default). */
  hashSettings?: boolean;
};

export type NormalizedRequest = {
  hash: string;
  prompt?: JsonValue;
  tools?: LedgerModelRequestTool[];
  toolChoice?: JsonValue;
  responseFormat?: JsonValue;
  settings?: Record<string, JsonValue>;
};

/**
 * Normalize a LanguageModelV3 call into the hashable core + display settings.
 * The core is built by whitelist so new SDK fields are ignored rather than
 * breaking existing fixtures.
 */
export function normalizeRequest(callOptions: unknown, options: NormalizeRequestOptions = {}): NormalizedRequest {
  const record = isRecord(callOptions) ? callOptions : {};
  const prompt = normalizePrompt(record.prompt);
  const tools = normalizeTools(record.tools);
  const toolChoice = record.toolChoice === undefined ? undefined : (asJson(record.toolChoice) as JsonValue);
  const responseFormat = record.responseFormat === undefined ? undefined : (asJson(record.responseFormat) as JsonValue);
  const settings = extractSettings(record);

  const core: Record<string, unknown> = {};
  if (prompt !== undefined) core.prompt = prompt;
  if (tools !== undefined) core.tools = tools;
  if (toolChoice !== undefined) core.toolChoice = toolChoice;
  if (responseFormat !== undefined) core.responseFormat = responseFormat;
  if (options.hashSettings && settings !== undefined) core.settings = settings;

  return {
    hash: hashRequest(core),
    ...(prompt !== undefined ? { prompt } : {}),
    ...(tools !== undefined ? { tools } : {}),
    ...(toolChoice !== undefined ? { toolChoice } : {}),
    ...(responseFormat !== undefined ? { responseFormat } : {}),
    ...(settings !== undefined ? { settings } : {}),
  };
}

export function toLedgerModelRequest(
  callOptions: unknown,
  model?: { provider?: string; modelId?: string },
  options?: NormalizeRequestOptions,
): LedgerModelRequest {
  const normalized = normalizeRequest(callOptions, options);
  return {
    ...normalized,
    ...(model?.provider ? { provider: model.provider } : {}),
    ...(model?.modelId ? { modelId: model.modelId } : {}),
  };
}

export function hashRequest(core: unknown): string {
  return `sha256:${createHash("sha256").update(stableStringify(core)).digest("hex")}`;
}

/**
 * Normalize a LanguageModelV3 prompt (message array). Keeps role and the
 * semantic content of each part; drops providerOptions at every level.
 */
export function normalizePrompt(prompt: unknown): JsonValue | undefined {
  if (!Array.isArray(prompt)) {
    return undefined;
  }
  return prompt.map((message) => normalizeMessage(message));
}

function normalizeMessage(message: unknown): JsonValue {
  if (!isRecord(message)) {
    return asJson(message) as JsonValue;
  }
  const role = typeof message.role === "string" ? message.role : "unknown";
  const content = message.content;
  if (typeof content === "string") {
    return { role, content };
  }
  if (Array.isArray(content)) {
    return { role, content: content.map((part) => normalizePart(part)) };
  }
  return { role };
}

function normalizePart(part: unknown): JsonValue {
  if (!isRecord(part)) {
    return asJson(part) as JsonValue;
  }
  const type = typeof part.type === "string" ? part.type : "unknown";
  switch (type) {
    case "text":
    case "reasoning":
      return { type, text: stringOr(part.text, "") };
    case "tool-call":
      return {
        type,
        toolCallId: stringOr(part.toolCallId, ""),
        toolName: stringOr(part.toolName, ""),
        input: normalizeToolInput(part.input),
      };
    case "tool-result": {
      const output = isRecord(part.output)
        ? ({ type: stringOr(part.output.type, "json"), value: asJson(part.output.value) } as JsonValue)
        : (asJson(part.output) as JsonValue);
      return {
        type,
        toolCallId: stringOr(part.toolCallId, ""),
        toolName: stringOr(part.toolName, ""),
        output,
      };
    }
    case "tool-approval-request":
      return {
        type,
        approvalId: stringOr(part.approvalId, ""),
        toolCallId: stringOr(part.toolCallId, ""),
      };
    case "tool-approval-response":
      return {
        type,
        approvalId: stringOr(part.approvalId, ""),
        approved: part.approved === true,
      };
    case "file":
      return {
        type,
        ...(typeof part.mediaType === "string" ? { mediaType: part.mediaType } : {}),
        dataDigest: digestFileData(part.data),
      };
    default: {
      const { providerOptions: _dropped, ...rest } = part;
      return asJson(rest) as JsonValue;
    }
  }
}

/**
 * Tool-call inputs appear as parsed objects in prompts but as stringified
 * JSON in model responses; normalize both to the parsed form so hashes agree.
 */
function normalizeToolInput(input: unknown): JsonValue {
  if (typeof input === "string") {
    try {
      return JSON.parse(input) as JsonValue;
    } catch {
      return input;
    }
  }
  return asJson(input) as JsonValue;
}

export function normalizeTools(tools: unknown): LedgerModelRequestTool[] | undefined {
  if (!Array.isArray(tools) || tools.length === 0) {
    return undefined;
  }
  return tools.map((tool) => normalizeTool(tool)).sort((left, right) => left.name.localeCompare(right.name));
}

function normalizeTool(tool: unknown): LedgerModelRequestTool {
  if (!isRecord(tool)) {
    return { name: String(tool) };
  }
  return {
    name: stringOr(tool.name, "unknown"),
    ...(typeof tool.description === "string" ? { description: tool.description } : {}),
    ...(tool.inputSchema !== undefined ? { inputSchema: normalizeJsonSchema(tool.inputSchema) } : {}),
  };
}

/** Strip the $schema marker so zod/SDK version bumps that only change the draft URL do not invalidate fixtures. */
export function normalizeJsonSchema(schema: unknown): JsonValue {
  if (Array.isArray(schema)) {
    return schema.map((item) => normalizeJsonSchema(item));
  }
  if (isRecord(schema)) {
    const output: Record<string, JsonValue> = {};
    for (const key of Object.keys(schema)) {
      if (key === "$schema") {
        continue;
      }
      output[key] = normalizeJsonSchema(schema[key]);
    }
    return output;
  }
  return asJson(schema) as JsonValue;
}

function extractSettings(callOptions: Record<string, unknown>): Record<string, JsonValue> | undefined {
  const settings: Record<string, JsonValue> = {};
  for (const key of SETTINGS_KEYS) {
    if (callOptions[key] !== undefined) {
      settings[key] = asJson(callOptions[key]) as JsonValue;
    }
  }
  return Object.keys(settings).length > 0 ? settings : undefined;
}

function digestFileData(data: unknown): string {
  if (typeof data === "string") {
    return `sha256:${createHash("sha256").update(data).digest("hex")}`;
  }
  if (data instanceof Uint8Array) {
    return `sha256:${createHash("sha256").update(data).digest("hex")}`;
  }
  if (data instanceof URL) {
    return `url:${data.href}`;
  }
  return `sha256:${createHash("sha256")
    .update(stableStringify(asJson(data)))
    .digest("hex")}`;
}

function stringOr(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

/** Best-effort JSON projection that drops undefined and non-JSON values predictably. */
function asJson(value: unknown): JsonValue | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => asJson(item) ?? null);
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (value instanceof URL) {
    return value.href;
  }
  if (isRecord(value)) {
    const output: Record<string, JsonValue> = {};
    for (const [key, child] of Object.entries(value)) {
      if (key === "providerOptions") {
        continue;
      }
      const converted = asJson(child);
      if (converted !== undefined) {
        output[key] = converted;
      }
    }
    return output;
  }
  return String(value);
}
