# Governance

`guardTools(tools, policy, options)` wraps an AI SDK tool set so policies are enforced **before** tool execution, and every decision leaves evidence in the ledger that CI can assert.

```ts
import { guardTools } from "actweave/govern";

const tools = guardTools(
  { lookupOrder, issueRefund },
  {
    allowTools: ["lookupOrder", "issueRefund"], // anything else is blocked
    approve: ["issueRefund"], // requires approval
    approver: ({ input }) => (input.amount > 500 ? { status: "denied", reason: "exceeds threshold" } : true),
    maxRisk: ["read", "write"], // allowed risk levels
    maxSteps: 8, // governed invocations per run
    sideEffects: "blocked-in-replay", // risk !== "read" blocked when mode: "replay"
    budget: { maxToolCalls: 20, maxCostUsd: 0.05 },
  },
  {
    recorder, // evidence events go here
    risk: { lookupOrder: "read", issueRefund: "write" },
    costs: { issueRefund: 0.01 }, // accrued against maxCostUsd
    onViolation: "throw", // or "error-result"
    mode: "live", // or "replay"
  },
);
```

Compose with recording so violations are captured in the run ledger too: `recordTools(guardTools(tools, policy, { recorder }), recorder)`.

## Violations

`onViolation: "throw"` (default) raises `GovernanceViolationError` with a typed `code`:

`tool-not-allowed` · `risk-exceeded` · `side-effect-blocked` · `max-steps` · `budget-tool-calls` · `budget-cost` · `approval-denied` · `approval-pending`

`onViolation: "error-result"` returns `{ governanceViolation: { code, tool, reason } }` as the tool result instead — the loop continues, the model's reaction is recorded, and the governed run stays fully replayable.

## Evidence events

| Event                                      | When                                  |
| ------------------------------------------ | ------------------------------------- |
| `governance.tool.requested`                | every governed invocation             |
| `governance.tool.allowed`                  | policy passed                         |
| `governance.tool.blocked`                  | violation (payload: `code`, `reason`) |
| `governance.approval.requested`/`resolved` | approver flow (payload: `status`)     |
| `safety.violation`                         | mirrors every block for audit queries |

Assert them in CI:

```ts
check(events).policyEnforced("tool-not-allowed");
check(events).approvalDenied("issueRefund");
expect(events).toHaveEnforcedPolicy(); // any enforcement
```

## Approvals

- With an `approver` callback, approvals resolve inline — deterministic in CI. The callback receives `{ tool, input, callId, callCount, costUsd }` and returns `true`/`false`/`"pending"` or `{ status, reason }`.
- Tools listed in `approve` **without** an approver get `needsApproval: true` and defer to the AI SDK's native two-call human-in-the-loop flow.

## Governance + replay

Pass `mode: "replay"` inside `assertReplayable` agent factories so `sideEffects: "blocked-in-replay"` engages. Because governance decisions are deterministic functions of policy + inputs, a recorded governed run replays with identical evidence — test that policies still hold by asserting `policyEnforced` on the replayed run's recorder.
