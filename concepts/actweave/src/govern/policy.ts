import type { RecorderToolRisk } from "../record/recorder.js";

export type GovernanceViolationCode =
  | "tool-not-allowed"
  | "risk-exceeded"
  | "side-effect-blocked"
  | "max-steps"
  | "budget-tool-calls"
  | "budget-cost"
  | "approval-denied"
  | "approval-pending";

export class GovernanceViolationError extends Error {
  readonly code: GovernanceViolationCode;
  readonly tool: string;

  constructor(code: GovernanceViolationCode, tool: string, message: string) {
    super(message);
    this.name = "GovernanceViolationError";
    this.code = code;
    this.tool = tool;
  }
}

export type ApprovalRequest = {
  tool: string;
  input: unknown;
  callId?: string;
  callCount: number;
  costUsd: number;
};

export type ApprovalDecision =
  | boolean
  | "approved"
  | "denied"
  | "pending"
  | { status: "approved" | "denied" | "pending"; reason?: string };

export type NormalizedApproval = { status: "approved" | "denied" | "pending"; reason?: string };

export function normalizeApprovalDecision(decision: ApprovalDecision): NormalizedApproval {
  if (decision === true) return { status: "approved" };
  if (decision === false) return { status: "denied" };
  if (typeof decision === "string") return { status: decision };
  return decision;
}

export type GovernancePolicy = {
  /** Disable all enforcement (default true = enabled). */
  enabled?: boolean;
  /** Allowlist: tools not in this list are blocked. */
  allowTools?: string[];
  /** Tools requiring approval before execution. */
  approve?: string[];
  /**
   * Approval resolver. With one, approvals resolve inline (CI-deterministic).
   * Without one, approved tools defer to the AI SDK's native needsApproval
   * two-call flow.
   */
  approver?: (request: ApprovalRequest) => ApprovalDecision | Promise<ApprovalDecision>;
  /** Allowed risk levels; tools with a risk outside the list are blocked. */
  maxRisk?: RecorderToolRisk[];
  /** Hard cap on governed tool invocations per run. */
  maxSteps?: number;
  /** Block side-effectful tools (risk other than "read"): always, or only in replay mode. */
  sideEffects?: "allowed" | "blocked-in-replay" | "blocked";
  budget?: {
    maxToolCalls?: number;
    maxCostUsd?: number;
  };
};

export type GovernanceState = {
  toolCalls: number;
  costUsd: number;
};

export type EnforcementContext = {
  tool: string;
  input: unknown;
  callId?: string;
  risk: RecorderToolRisk;
  mode: "live" | "replay";
  state: GovernanceState;
};

export type EnforcementResult = { ok: true } | { ok: false; code: GovernanceViolationCode; reason: string };

export function enforceAllowlist(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  if (policy.allowTools && !policy.allowTools.includes(context.tool)) {
    return {
      ok: false,
      code: "tool-not-allowed",
      reason: `tool "${context.tool}" is not in allowTools [${policy.allowTools.join(", ")}]`,
    };
  }
  return { ok: true };
}

export function enforceToolRisk(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  if (policy.maxRisk && !policy.maxRisk.includes(context.risk)) {
    return {
      ok: false,
      code: "risk-exceeded",
      reason: `tool "${context.tool}" has risk "${context.risk}" outside allowed [${policy.maxRisk.join(", ")}]`,
    };
  }
  return { ok: true };
}

export function enforceSideEffects(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  const sideEffectful = context.risk !== "read";
  if (!sideEffectful) {
    return { ok: true };
  }
  if (policy.sideEffects === "blocked") {
    return {
      ok: false,
      code: "side-effect-blocked",
      reason: `side-effectful tool "${context.tool}" (risk "${context.risk}") is blocked by policy`,
    };
  }
  if (policy.sideEffects === "blocked-in-replay" && context.mode === "replay") {
    return {
      ok: false,
      code: "side-effect-blocked",
      reason: `side-effectful tool "${context.tool}" (risk "${context.risk}") is blocked during replay`,
    };
  }
  return { ok: true };
}

export function enforceMaxSteps(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  if (policy.maxSteps !== undefined && context.state.toolCalls > policy.maxSteps) {
    return {
      ok: false,
      code: "max-steps",
      reason: `governed tool invocation #${context.state.toolCalls} exceeds maxSteps ${policy.maxSteps}`,
    };
  }
  return { ok: true };
}

export function enforceToolBudget(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  const max = policy.budget?.maxToolCalls;
  if (max !== undefined && context.state.toolCalls > max) {
    return {
      ok: false,
      code: "budget-tool-calls",
      reason: `tool call #${context.state.toolCalls} exceeds budget.maxToolCalls ${max}`,
    };
  }
  return { ok: true };
}

export function enforceCostBudget(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  const max = policy.budget?.maxCostUsd;
  if (max !== undefined && context.state.costUsd > max) {
    return {
      ok: false,
      code: "budget-cost",
      reason: `cumulative cost $${context.state.costUsd.toFixed(4)} exceeds budget.maxCostUsd ${max}`,
    };
  }
  return { ok: true };
}

const ENFORCERS = [
  enforceAllowlist,
  enforceToolRisk,
  enforceSideEffects,
  enforceMaxSteps,
  enforceToolBudget,
  enforceCostBudget,
] as const;

export function enforcePolicy(policy: GovernancePolicy, context: EnforcementContext): EnforcementResult {
  if (policy.enabled === false) {
    return { ok: true };
  }
  for (const enforce of ENFORCERS) {
    const result = enforce(policy, context);
    if (!result.ok) {
      return result;
    }
  }
  return { ok: true };
}
