import { describe, expect, it } from "vitest";
import { normalizeJsonSchema, normalizeRequest } from "../src/record/normalize.js";

const basePrompt = [
  { role: "system", content: "Resolve refunds." },
  { role: "user", content: [{ type: "text", text: "Can order 123 be refunded?" }] },
];

const baseTools = [
  {
    type: "function",
    name: "lookupOrder",
    description: "Look up an order",
    inputSchema: {
      $schema: "http://json-schema.org/draft-07/schema#",
      type: "object",
      properties: { orderId: { type: "string" } },
      required: ["orderId"],
      additionalProperties: false,
    },
  },
];

function baseRequest(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return { prompt: basePrompt, tools: baseTools, temperature: 0, ...overrides };
}

describe("request hash invariants", () => {
  const baseline = normalizeRequest(baseRequest()).hash;

  it("is stable across identical requests", () => {
    expect(normalizeRequest(baseRequest()).hash).toBe(baseline);
  });

  it("ignores sampling settings, headers, and providerOptions by default", () => {
    expect(normalizeRequest(baseRequest({ temperature: 0.9 })).hash).toBe(baseline);
    expect(normalizeRequest(baseRequest({ topP: 0.5, maxOutputTokens: 100, seed: 7 })).hash).toBe(baseline);
    expect(normalizeRequest(baseRequest({ headers: { authorization: "Bearer abc" } })).hash).toBe(baseline);
    expect(normalizeRequest(baseRequest({ providerOptions: { openai: { store: true } } })).hash).toBe(baseline);
  });

  it("includes settings in the hash when hashSettings is set", () => {
    const strict = normalizeRequest(baseRequest(), { hashSettings: true }).hash;
    expect(normalizeRequest(baseRequest({ temperature: 0.9 }), { hashSettings: true }).hash).not.toBe(strict);
  });

  it("changes when the system text changes", () => {
    const prompt = [{ role: "system", content: "Resolve refunds politely." }, basePrompt[1]];
    expect(normalizeRequest(baseRequest({ prompt })).hash).not.toBe(baseline);
  });

  it("changes when a tool description or schema changes", () => {
    const renamedDescription = [{ ...baseTools[0], description: "Look up an order by id" }];
    expect(normalizeRequest(baseRequest({ tools: renamedDescription })).hash).not.toBe(baseline);

    const widerSchema = [
      {
        ...baseTools[0],
        inputSchema: {
          ...baseTools[0].inputSchema,
          properties: { orderId: { type: "string" }, force: { type: "boolean" } },
        },
      },
    ];
    expect(normalizeRequest(baseRequest({ tools: widerSchema })).hash).not.toBe(baseline);
  });

  it("changes when toolChoice or responseFormat changes", () => {
    expect(normalizeRequest(baseRequest({ toolChoice: { type: "required" } })).hash).not.toBe(baseline);
    expect(normalizeRequest(baseRequest({ responseFormat: { type: "json" } })).hash).not.toBe(baseline);
  });

  it("changes when messages are reordered", () => {
    const prompt = [basePrompt[1], basePrompt[0]];
    expect(normalizeRequest(baseRequest({ prompt })).hash).not.toBe(baseline);
  });

  it("is insensitive to tool declaration order", () => {
    const secondTool = { type: "function", name: "issueRefund", inputSchema: { type: "object" } };
    const forward = normalizeRequest(baseRequest({ tools: [...baseTools, secondTool] })).hash;
    const reversed = normalizeRequest(baseRequest({ tools: [secondTool, ...baseTools] })).hash;
    expect(reversed).toBe(forward);
  });

  it("treats string and object tool-call inputs as the same", () => {
    const withObjectInput = [
      ...basePrompt,
      {
        role: "assistant",
        content: [{ type: "tool-call", toolCallId: "c1", toolName: "lookupOrder", input: { orderId: "123" } }],
      },
    ];
    const withStringInput = [
      ...basePrompt,
      {
        role: "assistant",
        content: [
          { type: "tool-call", toolCallId: "c1", toolName: "lookupOrder", input: JSON.stringify({ orderId: "123" }) },
        ],
      },
    ];
    expect(normalizeRequest(baseRequest({ prompt: withStringInput })).hash).toBe(
      normalizeRequest(baseRequest({ prompt: withObjectInput })).hash,
    );
  });

  it("ignores the $schema marker in tool schemas", () => {
    const draft2020 = [
      {
        ...baseTools[0],
        inputSchema: { ...baseTools[0].inputSchema, $schema: "https://json-schema.org/draft/2020-12/schema" },
      },
    ];
    expect(normalizeRequest(baseRequest({ tools: draft2020 })).hash).toBe(baseline);
  });

  it("records settings for display without hashing them", () => {
    const normalized = normalizeRequest(baseRequest({ temperature: 0.7, seed: 42 }));
    expect(normalized.settings).toEqual({ temperature: 0.7, seed: 42 });
  });
});

describe("normalizeJsonSchema", () => {
  it("strips $schema recursively", () => {
    expect(
      normalizeJsonSchema({
        $schema: "http://json-schema.org/draft-07/schema#",
        type: "object",
        properties: { nested: { $schema: "x", type: "string" } },
      }),
    ).toEqual({ type: "object", properties: { nested: { type: "string" } } });
  });
});
