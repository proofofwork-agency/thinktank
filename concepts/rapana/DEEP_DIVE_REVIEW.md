# Rapana — Adversarial Deep-Dive Review

_Autonomous overnight review by Claude (Opus 4.8) on top of the opencode build.
2026-06-23._

## Method

Two multi-agent workflows audited the codebase, **one auditor per safety-critical
dimension**, and **every finding was adversarially re-verified against the actual
code** before it counted (a skeptic agent tried to refute each one). Reviewers and
verifiers were independent.

- **Pass 1 (core, 10 dimensions):** risk/guardrails, execution safety, MEXC client +
  secrets, strategy/indicator math, backtest, fleet orchestration, agents, ledger,
  test gaps, CLI/config → **60 confirmed of 72** (4 critical, 8 high, 16 medium, …).
- **Pass 2 (the files opencode added after pass 1 started):** live_safety, runner/replay,
  performance/notify, new tests → **15 confirmed of 18** (0 critical/high, 5 medium, …).

The 4 "critical" were the **same** bug found by 4 dimensions. Net unique high-impact
issues were small in number but real — several were numerically reproduced by the
verifiers.

## What I fixed (committed)

Baseline `aa5a095` → fixes in `8295123`, `4b6b273`, `d3c7d99`. **90/90 tests pass,
`ruff` clean.** Each fix has a regression test in `tests/test_review_regressions.py`.

| Sev | Area | Bug | Fix |
|-----|------|-----|-----|
| **CRIT** | risk | Daily-loss circuit breaker read `avg_cost` **after** the fill flattened the position, so closing-sell **losses recorded as profits** — the kill-switch could never trip on a loss. Wired into paper **and** live gating. | Feed the breaker the portfolio's signed realized-PnL delta, captured inside `_apply_fill`. |
| HIGH | risk | `OrderRateLimiter` never wired in → `max_orders_per_min` unenforced. | Limiter built on the fleet, consulted in the gate, consumed on real submission. |
| HIGH | backtest | Partial position reductions booked **no** trade / realized PnL. | Realize PnL on every sell/reduction. |
| HIGH | capital | Paper mode deployed **1%** (not the documented full balance), silently blocking nearly all paper/replay buys. | Paper = full balance; staging is live-only. **⚠ behavior change.** |
| HIGH | ledger | `verify_chain()` **raised** on a torn/tampered line instead of returning `False`. | Malformed line ⇒ corruption ⇒ `False`. |
| HIGH | replay | `ReplayProvider` revealed the cursor bar and filled at its close — **same-bar lookahead** in the pre-live validation gate. | Reveal only closed bars `[0, cursor)`, matching `BacktestEngine`. |
| MED | metrics | Sortino = **NaN** (invalid JSON) with no losing bars; `win_rate` denominator counted zero-PnL buy legs. | Finite Sortino stand-in; win_rate over decided trades only. |
| MED | signals | Neutral signals diluted the confidence-weighted consensus. | Excluded from the weighted average. |
| LOW | runner | `ZeroDivisionError` if `bars_per_day`/`digest_every` is 0. | Guarded. |
| — | packaging | `.gitignore` `data/` ignored the **`rapana/data/` source package** (broke a fresh clone) and hid 2 ruff issues. | Anchored to `/data/`; lint fixed. Also ignored `.contextrelay/` + `.engram/` (held tokens). |

## ⚠ Behavior change to confirm

**Paper mode now trades the full simulated balance** instead of 1%. This matches the
`StagedCapital` docstring, the verified finding, and the CLI design (staging is built
only via `StagedCapital(paper=False)` in `promote`/`demote`/`live-check`). Three tests
that asserted the old 1% behavior were corrected. If you intended paper to mirror the
live 1% ramp, revert `rapana/fleet/capital.py` + those tests.

## Deferred — your call (NOT fixed)

The live order path is **un-wired today** (both CLI fleet builders hardcode
`PaperExecutor`; `LiveGuard`/`LiveExecutor` appear only in tests). So the items below
**cannot move real money in the current code** — but they should be hardened *before*
anyone wires live execution.

**Live-safety (latent until live is wired):**
- `live_safety.preflight` "withdraw disabled" check is a hardcoded `True` — a comment,
  not a control. Recommend a `RAPANA_WITHDRAW_VERIFIED` env flag defaulting **False**
  (fail-closed), optionally plus a MEXC account-permission probe.
- `LiveGuard` api-key preflight reads `client.apiKey` (always `None`; the key lives at
  `client.exchange.apiKey`). Fails-closed by accident today; fix the attribute path
  when hardening.
- `LiveGuard` mints a fresh `clientOrderId` each call, so a retried order **double-fills**.
  Needs a stable per-logical-order id.
- `LiveExecutor` ignores cash sufficiency on a live buy; `reconcile()` returns `{}` on
  fetch failure (conflates error with empty balance).

**Correctness / design (need a product decision):**
- **Live data repaint:** the live/scheduled paper path (`StoreDataProvider.get_history`)
  can include the current forming bar — the same lookahead class I fixed in replay, but
  in the live path. Recommend dropping the last (unclosed) bar for indicators. _(Highest
  priority of the deferred items.)_
- **Circuit breaker scope:** only tracks **realized** PnL and anchors to construction-time
  equity. A large **open-position** drawdown can exceed `max_daily_loss_pct` without
  tripping, and the limit never re-baselines per day. Recommend a mark-to-market check.
- **Ledger anchor:** `verify_chain` proves only internal consistency — a full-file rewrite
  passes. Recommend HMAC/signature or an external head checkpoint.
- **`performance.win_rate`** nets multiple trades per cycle and drops break-even closes,
  distorting the metric used to gate live promotion. Needs per-trade realized-PnL plumbing.

Full per-finding detail (with verifier reasoning) is in the workflow transcripts under
`.../subagents/workflows/` for run IDs `wf_69abe8c4-b21` and `wf_0e664a7b-b51`.
