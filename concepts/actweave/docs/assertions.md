# Assertions

## check()

`check(source)` accepts a `LedgerEvent[]`, anything with an `events()` method (recorders, ledgers), or an AI SDK result object (converted via `resultToLedgerEvents` — derived events support assertions but not strict replay).

```ts
import { check } from "actweave";

check(events)
  .completed() // a run.completed event exists
  .noErrors() // no error events or *.failed types
  .called("lookupOrder")
  .notCalled("issueRefund")
  .calledTimes("lookupOrder", 1)
  .calledWith("lookupOrder", { orderId: "123" }) // partial match
  .calledWith("lookupOrder", (input) => input.orderId.startsWith("1")) // predicate
  .toolCallOrder(["lookupOrder", "auditDecision"]) // ordered subsequence
  .eventSequence(["run.started", "tool.called", "run.completed"])
  .hasEvent("governance.tool.blocked")
  .validLifecycle() // start/complete pairs, single terminal event
  .outputContains("expired")
  .outputMatches(/cannot be refunded/i)
  .durationBelow(5000) // wall-clock; meaningless under deterministic recording
  .policyEnforced("approval-denied")
  .approvalDenied("issueRefund");
```

All assertions throw with a specific message on failure and chain on success.

## Golden fixtures

```ts
check(events).toMatchGolden("test/fixtures/refund.jsonl");
```

- Missing fixture → written (review and commit it).
- `ACTWEAVE_UPDATE_GOLDEN=1` → rewritten.
- Otherwise → compared (event types, tool sequence/inputs/outputs, run output, errors) and failed with itemized issues.

`compareLedgerEvents` / `compareRuns` options: `compareOutputs: false` to ignore output drift, `allowSideEffects: true` to permit side-effectful calls, and (compareRuns) `ignorePaths` / `normalizers` for volatile fields.

## Vitest matchers

```ts
import { expect } from "vitest";
import { extendActweaveMatchers } from "actweave/vitest";

extendActweaveMatchers(expect);

expect(events).toBeCompletedRun();
expect(events).toHaveCalledTool("lookupOrder", { orderId: "123" });
expect(events).toHaveEventSequence(["run.started", "run.completed"]);
expect(events).toHaveNoErrors();
expect(events).toHaveValidLifecycle();
expect(events).toHaveEnforcedPolicy("tool-not-allowed");
expect(events).toMatchGolden("test/fixtures/refund.jsonl");
await expect("test/fixtures/refund.jsonl").toBeReplayable({ agent: buildAgent });
```

For matcher typing, augment vitest in a `.d.ts`:

```ts
import type { ActweaveMatchers } from "actweave/vitest";

declare module "vitest" {
  interface Matchers<T = any> extends ActweaveMatchers<T> {}
}
```

## Ledger-to-ledger matching

`assertLedgerMatches(expectedSource, actualSource, options)` compares two fixtures/event arrays directly (paths or arrays) — useful for comparing a re-recorded run against the committed one outside of replay.
