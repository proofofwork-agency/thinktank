import { isRecord } from "../internal/guards.js";
import type { LedgerRecorder, RecorderToolRisk } from "../record/recorder.js";
import {
  GovernanceViolationError,
  enforcePolicy,
  normalizeApprovalDecision,
  type EnforcementContext,
  type GovernancePolicy,
  type GovernanceState,
  type GovernanceViolationCode,
} from "./policy.js";

export type GuardToolsOptions = {
  /** Record governance evidence events into this recorder's ledger. */
  recorder?: LedgerRecorder;
  /** Risk level per tool name (default "unknown" — treated as side-effectful). */
  risk?: Record<string, RecorderToolRisk>;
  /** Per-invocation cost per tool name, accrued against budget.maxCostUsd. */
  costs?: Record<string, number>;
  /**
   * throw (default): violations raise GovernanceViolationError.
   * error-result: violations are returned as the tool result so the loop
   * continues and the model's reaction is itself recorded.
   */
  onViolation?: "throw" | "error-result";
  /** Mark replay runs so sideEffects: "blocked-in-replay" engages. */
  mode?: "live" | "replay";
};

type ToolExecuteOptions = {
  toolCallId?: string;
  [key: string]: unknown;
};

/**
 * Wrap an AI SDK tool set with governance enforced before execution:
 * allowlists, risk caps, side-effect blocking, invocation/cost budgets, and
 * approval gates — each decision leaving evidence events in the ledger
 * (governance.tool.requested/allowed/blocked, governance.approval.*,
 * safety.violation) that CI can assert with check(...).policyEnforced().
 */
export function guardTools<TTools extends Record<string, unknown>>(
  tools: TTools,
  policy: GovernancePolicy,
  options: GuardToolsOptions = {},
): TTools {
  const state: GovernanceState = { toolCalls: 0, costUsd: 0 };
  const wrapped: Record<string, unknown> = {};
  for (const [name, tool] of Object.entries(tools)) {
    wrapped[name] = wrapTool(name, tool, policy, options, state);
  }
  return wrapped as TTools;
}

function wrapTool(
  name: string,
  tool: unknown,
  policy: GovernancePolicy,
  options: GuardToolsOptions,
  state: GovernanceState,
): unknown {
  if (!isRecord(tool) || typeof tool.execute !== "function") {
    return tool;
  }
  const execute = tool.execute as (input: unknown, execOptions?: ToolExecuteOptions) => unknown;
  const enabled = policy.enabled !== false;
  const needsApprovalWithoutApprover = enabled && !policy.approver && (policy.approve ?? []).includes(name);

  const guarded = {
    ...tool,
    // no approver callback: defer to the AI SDK's native two-call HITL flow
    ...(needsApprovalWithoutApprover ? { needsApproval: true } : {}),
    execute: async (input: unknown, execOptions?: ToolExecuteOptions) => {
      const callId = typeof execOptions?.toolCallId === "string" ? execOptions.toolCallId : undefined;
      const risk = options.risk?.[name] ?? "unknown";

      if (!enabled) {
        return execute(input, execOptions);
      }

      state.toolCalls += 1;
      state.costUsd += options.costs?.[name] ?? 0;

      const context: EnforcementContext = {
        tool: name,
        input,
        callId,
        risk,
        mode: options.mode ?? "live",
        state,
      };

      await emit(options.recorder, "governance.tool.requested", name, callId, {
        risk,
        toolCalls: state.toolCalls,
        costUsd: state.costUsd,
      });

      const enforcement = enforcePolicy(policy, context);
      if (!enforcement.ok) {
        return violate(options, name, callId, enforcement.code, enforcement.reason);
      }

      if ((policy.approve ?? []).includes(name) && policy.approver) {
        await emit(options.recorder, "governance.approval.requested", name, callId, { input });
        const decision = normalizeApprovalDecision(
          await policy.approver({ tool: name, input, callId, callCount: state.toolCalls, costUsd: state.costUsd }),
        );
        await emit(options.recorder, "governance.approval.resolved", name, callId, {
          status: decision.status,
          reason: decision.reason,
        });
        if (decision.status === "denied") {
          return violate(options, name, callId, "approval-denied", decision.reason ?? `approval denied for "${name}"`);
        }
        if (decision.status === "pending") {
          return violate(
            options,
            name,
            callId,
            "approval-pending",
            decision.reason ?? `approval for "${name}" is pending`,
          );
        }
      }

      await emit(options.recorder, "governance.tool.allowed", name, callId, { risk });
      return execute(input, execOptions);
    },
  };
  return guarded;
}

async function violate(
  options: GuardToolsOptions,
  tool: string,
  callId: string | undefined,
  code: GovernanceViolationCode,
  reason: string,
): Promise<unknown> {
  await emit(options.recorder, "governance.tool.blocked", tool, callId, { code, reason });
  await emit(options.recorder, "safety.violation", tool, callId, { code, reason });
  if (options.onViolation === "error-result") {
    return { governanceViolation: { code, tool, reason } };
  }
  throw new GovernanceViolationError(code, tool, `Governance violation (${code}): ${reason}`);
}

async function emit(
  recorder: LedgerRecorder | undefined,
  type: string,
  name: string,
  callId: string | undefined,
  payload: Record<string, unknown>,
): Promise<void> {
  if (!recorder) {
    return;
  }
  await recorder.append({ type, name, callId, payload });
}
