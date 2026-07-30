# Sprint 1B — Stop the taker bleed safely + capture idle yield

**Status:** GREENLIT 2026-06-24 (human: "continue to the next part"). Work starts after a context clear.
**Branch:** continue on `sprint-1-structural-value` (or cut a fresh `sprint-1b-*` branch — decide at start).
**Roles:** Codex builds, Claude reviews + commits. Claude is the sole git-writer (ContextRelay policy: `agentsMayWriteGit: {claude: true, codex: false}`). Codex leaves diffs uncommitted for Claude.

## Why this part (the honest money story)
Sprint 1 Phase 1A (committed: `5a1f31c`, `547b02d`, `959a45b`, `3e4d1b4`) added the honesty + safety rails but moved **zero** dollars. Phase 1B is the part that actually moves dollars — modestly and honestly:
- **Stop paying ~0.1% taker fees** on every trade (maker post-only path).
- **Capture the ~3.5% idle-cash yield** instead of holding 0%-yield USDT (sweep — the single biggest real dollar item).

No new alpha — none exists (6/6 strategy families failed the honest DSR gate; funding-spike re-confirmed FAIL at DSR 0.694 on real data 2026-06-24). This is cost-reduction + savings yield + safe live wiring, NOT a price-prediction edge.

## Part A — Maker order path (the #1 money item; highest execution risk)
**THE core landmine:** today `execute()` returns a binary `Fill | None`. `None` conflates "rejected" vs "resting unfilled", and `Fill` has no order-id / status / partial-fill state. Maker (post-only) orders can rest unfilled or partial-fill, so the **contract must change first** — that's the real risk, more than the ccxt mechanics.

1. **Order-result contract:** replace `Fill | None` with an explicit result (status: `filled | partial | resting | rejected | canceled`; order-id; `filled_qty` vs `proposed_qty`). Every downstream consumer (exposure tracking, circuit-breaker accounting, reflection-memory attribution) must tolerate "decided but not filled".
2. **MexcClient wrappers:** `create_order` (post-only → `LIMIT_MAKER`), `fetch_order`, `cancel_order`. Idempotent `clientOrderId` (reuse `live_safety.py:96` pattern). Bounded poll/timeout; cancel on timeout.
3. **Partial-fill accounting** books the FILLED qty, never the proposed qty. Submission consumes rate-limit + cancel-ratio budget even on no-fill.
4. **Default behavior: post-only-or-skip, NO taker fallback.** A missed trade ~costs nothing on an unproven edge; a taker fallback re-imports the exact bleed we're removing. "Skip" must mean NO open order remains.
5. **Telemetry:** `maker_submitted / filled / partial / canceled / missed_fill`.
6. **Paper/sim first**, live only behind contract tests + the existing `preflight()` gate.
7. **Fix the LiveGuard api-key bug:** `risk/live_safety.py` preflight reads `self.inner.client.apiKey`, but the real key is at `client.exchange.apiKey` (ccxt) → currently would falsely block every live order.
8. **Live wiring flip stays GATED:** `cli.py` currently builds `ExecutionTrader(PaperExecutor())` even in live mode. The flip to `LiveExecutor` waits behind contract tests + `preflight()` + explicit human go.

## Part B — Idle-yield sweep (biggest dollar item; OUTWARD action — needs human + credentials)
Sweep idle USDT to MEXC Earn / sUSDS to capture ~3.5%. This is an **outward financial action** (new API surface: subscribe/redeem; real money leaves the spot balance). Requires API + credentials + **explicit human authorization**, must be reversible/auditable, and keep enough liquid for trading. Sprint 1 already SURFACES the drag (telemetry via `estimate_idle_cash_drag`); this CAPTURES it. Design wrappers + a dry-run/paper path first; the actual sweep waits on human go.

## Sequence + risk order
1. Part A maker path in **PAPER/SIM first** — land the contract change + order wrappers behind tests, no live wiring.
2. Fix the LiveGuard api-key bug as part of Part A.
3. Part B (yield sweep) design + dry-run; the outward sweep waits on explicit human authorization + credentials.
4. Live wiring flip **last**, gated.

## Verification
- `uv run pytest -q` green (contract + reconcile tests); `uv run ruff check .` clean.
- Paper/sim proves: post-only-or-skip leaves NO resting order on skip; partial-fill books the filled qty.
- No live order placed until contract tests + `preflight()` pass AND the human says go.
- No source touches to withdraw/transfer endpoints without explicit human authorization.

## Key files
`rapana/fleet/execution.py` (Fill contract, LiveExecutor) · `rapana/mexc/client.py` (order wrappers) · `rapana/risk/live_safety.py` (LiveGuard + api-key bug + clientOrderId) · `rapana/fleet/orchestrator.py` (tolerate not-filled) · `rapana/cli.py` (live wiring flip — gated) · `rapana/config.py`.
