import { describe, expect, it } from "vitest";
import { ToolLoopAgent, stepCountIs, tool } from "ai";
import { MockLanguageModelV3 } from "ai/test";
import type { LanguageModelV3GenerateResult } from "@ai-sdk/provider";
import { z } from "zod";

import { createRecorder } from "../../src/record/recorder.js";
import { recordModel } from "../../src/record/model.js";
import { recordTools } from "../../src/record/tools.js";
import { check } from "../../src/check/index.js";
import { GovernanceViolationError, guardTools } from "../../src/govern/index.js";
import { assertReplayable } from "../../src/replay/index.js";
import { extendActweaveMatchers } from "../../src/vitest.js";

extendActweaveMatchers(expect);

function response(
  content: LanguageModelV3GenerateResult["content"],
  unified: "tool-calls" | "stop",
): LanguageModelV3GenerateResult {
  return {
    content,
    finishReason: { unified, raw: unified },
    usage: {
      inputTokens: { total: 1, noCache: undefined, cacheRead: undefined, cacheWrite: undefined },
      outputTokens: { total: 1, text: undefined, reasoning: undefined },
    },
    warnings: [],
  };
}

function scriptedModel(responses: LanguageModelV3GenerateResult[]): MockLanguageModelV3 {
  let call = 0;
  return new MockLanguageModelV3({
    doGenerate: async () => {
      const next = responses[call++];
      if (!next) throw new Error("scripted model exhausted");
      return next;
    },
  });
}

const refundToolCall = response(
  [{ type: "tool-call", toolCallId: "call-1", toolName: "issueRefund", input: JSON.stringify({ amount: 900 }) }],
  "tool-calls",
);
const finalAnswer = response([{ type: "text", text: "Refund processed." }], "stop");

function refundTools() {
  return {
    issueRefund: tool({
      description: "Issue a refund",
      inputSchema: z.object({ amount: z.number() }),
      execute: async ({ amount }: { amount: number }) => ({ refunded: amount }),
    }),
    lookupOrder: tool({
      description: "Look up an order",
      inputSchema: z.object({ orderId: z.string() }),
      execute: async ({ orderId }: { orderId: string }) => ({ orderId }),
    }),
  };
}

describe("guardTools", () => {
  it("blocks tools outside the allowlist and records evidence", async () => {
    const recorder = createRecorder({ deterministic: true });
    const tools = guardTools(refundTools(), { allowTools: ["lookupOrder"] }, { recorder });

    await expect(
      (tools.issueRefund as { execute: (input: unknown, opts?: unknown) => Promise<unknown> }).execute(
        { amount: 900 },
        { toolCallId: "call-1" },
      ),
    ).rejects.toThrow(GovernanceViolationError);

    const events = [...recorder.events()];
    check(events).policyEnforced("tool-not-allowed");
    expect(events).toHaveEnforcedPolicy("tool-not-allowed");
    expect(events.map((event) => event.type)).toEqual([
      "governance.tool.requested",
      "governance.tool.blocked",
      "safety.violation",
    ]);
  });

  it("enforces risk levels, budgets, and step caps", async () => {
    const recorder = createRecorder({ deterministic: true });
    const tools = guardTools(
      refundTools(),
      { maxRisk: ["read"], budget: { maxToolCalls: 2, maxCostUsd: 0.05 } },
      { recorder, risk: { issueRefund: "write", lookupOrder: "read" }, costs: { lookupOrder: 0.04 } },
    );
    const lookup = tools.lookupOrder as { execute: (input: unknown, opts?: unknown) => Promise<unknown> };
    const refund = tools.issueRefund as { execute: (input: unknown, opts?: unknown) => Promise<unknown> };

    await expect(refund.execute({ amount: 1 }, { toolCallId: "c0" })).rejects.toThrow(/risk-exceeded/);
    await lookup.execute({ orderId: "1" }, { toolCallId: "c1" });
    // third governed invocation exceeds maxToolCalls=2
    await expect(lookup.execute({ orderId: "2" }, { toolCallId: "c2" })).rejects.toThrow(/budget-tool-calls|max-steps/);

    check(recorder.events() as never).policyEnforced("risk-exceeded");
  });

  it("resolves approvals inline via the approver callback", async () => {
    const recorder = createRecorder({ deterministic: true });
    const tools = guardTools(
      refundTools(),
      {
        approve: ["issueRefund"],
        approver: ({ input }) =>
          (input as { amount: number }).amount > 500 ? { status: "denied", reason: "amount exceeds threshold" } : true,
      },
      { recorder },
    );
    const refund = tools.issueRefund as { execute: (input: unknown, opts?: unknown) => Promise<unknown> };

    await expect(refund.execute({ amount: 900 }, { toolCallId: "c1" })).rejects.toThrow(/approval-denied/);
    await expect(refund.execute({ amount: 100 }, { toolCallId: "c2" })).resolves.toEqual({ refunded: 100 });

    check(recorder.events() as never)
      .policyEnforced("approval-denied")
      .approvalDenied("issueRefund");
  });

  it("defers to native needsApproval when no approver is configured", () => {
    const tools = guardTools(refundTools(), { approve: ["issueRefund"] });
    expect((tools.issueRefund as { needsApproval?: boolean }).needsApproval).toBe(true);
    expect((tools.lookupOrder as { needsApproval?: boolean }).needsApproval).toBeUndefined();
  });

  it("error-result mode feeds the violation back to the model and the run is recordable + replayable", async () => {
    // record a governed run where the model insists on a forbidden tool;
    // recordTools wraps guardTools so the violation result is captured too
    const recorder = createRecorder({ deterministic: true });
    const guarded = recordTools(
      guardTools(refundTools(), { allowTools: ["lookupOrder"] }, { recorder, onViolation: "error-result" }),
      recorder,
    );
    const agent = new ToolLoopAgent({
      model: recordModel(scriptedModel([refundToolCall, finalAnswer]), recorder),
      instructions: "Process refunds.",
      tools: guarded,
      stopWhen: stepCountIs(5),
    });
    await recorder.run("Refund order 123", () => agent.generate({ prompt: "Refund order 123" }), {
      agentName: "refunds",
    });
    const { events } = await recorder.close();

    // the violation surfaced as the tool result, the model saw it, the loop continued
    check(events).completed().policyEnforced("tool-not-allowed");
    const toolCompleted = events.find((event) => event.type === "tool.completed");
    expect(toolCompleted?.output).toMatchObject({ governanceViolation: { code: "tool-not-allowed" } });

    // and the governed run replays keylessly with the same governance outcome
    const replayRecorder = createRecorder({ deterministic: true });
    await assertReplayable(events, {
      agent: (model) =>
        new ToolLoopAgent({
          model,
          instructions: "Process refunds.",
          tools: recordTools(
            guardTools(
              refundTools(),
              { allowTools: ["lookupOrder"] },
              { recorder: replayRecorder, onViolation: "error-result", mode: "replay" },
            ),
            replayRecorder,
          ),
          stopWhen: stepCountIs(5),
        }),
    });
    check(replayRecorder.events() as never).policyEnforced("tool-not-allowed");
  });

  it("blocks side-effectful tools in replay mode only when configured", async () => {
    const policy = { sideEffects: "blocked-in-replay" as const };
    const live = guardTools(refundTools(), policy, { risk: { issueRefund: "write" }, mode: "live" });
    const replay = guardTools(refundTools(), policy, { risk: { issueRefund: "write" }, mode: "replay" });

    await expect(
      (live.issueRefund as { execute: (i: unknown, o?: unknown) => Promise<unknown> }).execute({ amount: 1 }),
    ).resolves.toEqual({ refunded: 1 });
    await expect(
      (replay.issueRefund as { execute: (i: unknown, o?: unknown) => Promise<unknown> }).execute({ amount: 1 }),
    ).rejects.toThrow(/side-effect-blocked/);
  });

  it("disabled policy passes everything through", async () => {
    const tools = guardTools(refundTools(), { enabled: false, allowTools: [] });
    await expect(
      (tools.issueRefund as { execute: (i: unknown, o?: unknown) => Promise<unknown> }).execute({ amount: 1 }),
    ).resolves.toEqual({ refunded: 1 });
  });
});
