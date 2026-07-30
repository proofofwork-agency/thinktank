# rapana — Research Closure

**Date:** 2026-06-24
**Decision:** HALT (clean pause). Joint Claude + Codex recommendation; authorized by the human ("park everything").
**Status of live trading:** PARKED. No live wiring, no real capital. Branch `sprint-1-structural-value` is local-only; push/merge is human-gated.

---

## 1. The decision in one line

rapana set out to find a trading **edge** and rigorously proved there isn't one reachable with **free data + retail (1h / REST) infrastructure**. That is a real, valuable result — it prevented the deployment of six-plus tempting-but-fake edges — but it means rapana, as built, is a **loss-prevention system, not a money-maker.** We are halting the alpha hunt and documenting the falsification.

---

## 2. What was tested — and falsified

Every strategy family was run through the same honest gate (deflated Sharpe ratio + drift/random-entry benchmark + walk-forward + locked holdout + pre-registration). All failed once drift-corrected:

| Family | Verdict | Evidence |
|---|---|---|
| Directional TA | FAIL | no skill vs drift |
| Funding carry (C2) | FAIL / NO-GO | majors + liquid alts, Codex-confirmed |
| 8 bar-TA strategies | FAIL | global-DSR gate |
| Funding-spike | FAIL | event-study gate |
| Cross-sectional rotation | FAIL | global DSR ~0.10 (a narrow-grid "PASS" was a survivorship + multiple-testing false positive) |
| Token-unlock events | FAIL | grand-union DSR ~0.005 (a +4.4%/event tilt was a 5-token/2025 concentration artifact) |
| Funding-fade | FAIL | reproduced DSR ~0.694 (earlier "validated" claim was false) |
| Gap / breakout / RSI triggers (alpha-hunt track) | FAIL | per-symbol best skill-DSR ~0.532, pooled ~0.474 (gate 0.95) |
| Sentiment (Fear&Greed) / CoinGecko macro / LLM regime | no edge | advisory only; fenced, fail-soft, off-by-default; LLM regime is a price-recombiner |

**Common cause:** all of these use free, widely-available price/funding/sentiment data. That information is already arbitraged, so after honest correction none beats random entry net of costs.

The validation machinery itself is the project's most valuable asset — it repeatedly caught false positives (concentration, survivorship, multiple-testing) that would otherwise have looked like edges.

---

## 3. The one validated positive: maker execution (a cost layer, not an edge)

The Sprint-1B maker offset sweep (real stored MEXC 1h, BTC/ETH/SOL, full year 2025-06-23 → 2026-06-23, 8759 bars/symbol; replay/paper only; artifact: `research/maker_offset_sweep_2026-06-24.json`):

| offset bps | maker eq | taker eq | net | fee floor | modeled px-impr | fill rate |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 9418.67 | 9175.96 | 242.71 | 173.04 | 173.04 | 97.6% |
| 0.5 | 9410.65 | 9175.96 | 234.69 | 173.02 | 190.33 | 96.1% |
| 1 | 9412.47 | 9175.96 | 236.52 | 173.27 | 207.92 | 94.9% |
| 1.5 | 9427.81 | 9175.96 | 251.86 | 173.26 | 225.24 | 94.4% |
| **2** | **9428.31** | **9175.96** | **252.35** | **173.01** | **242.21** | **93.4%** |
| 3 | 9415.60 | 9175.96 | 239.64 | 172.98 | 276.77 | 91.3% |
| 5 | 9553.22 | 9175.96 | 377.26 | 176.52 | 353.03 | 87.7% |
| 8 | 9427.25 | 9175.96 | 251.29 | 172.65 | 448.89 | 80.9% |
| 12 | 9569.81 | 9175.96 | 393.85 | 175.15 | 595.52 | 72.6% |

**Verdict (signed Claude + Codex): GO** to keep maker execution as a prospective **cost-reduction layer**; **NO-GO** as a money-maker or a reason to go live for profit.

Why:
- **Both maker and taker end the year DOWN.** Primary 3-symbol @2bps: maker `9428.31` vs taker `9175.96` from `10000` (the strategy lost ~6–8%; maker just lost ~2.5% less). 12-symbol universe @2bps: maker `7649.20` vs taker `7440.99` (lost ~24–26%). **This is cost reduction on a losing fleet, not profit.**
- The **durable** part is `fee floor` = gross fee savings ≈ **173 (~1.7% on 10k)**, and only if the real MEXC schedule is taker 10 bps / maker 5 bps. Confirm the actual fee/rebate tiers before relying on it.
- The `modeled px-impr` column is **formula-derived** (`filled_notional × (0.0005 + offset/10000)`) — an assumed slippage-savings + offset credit with **no queue / adverse-selection** modeling. It is optimistic and would erode live. It is **not** measured venue fill quality.
- Robustness (genuine): net positive across all 9 offsets, all 3 symbols individually (2/3/5 bps), and both half-years; not concentrated; path/missed-fill residual is *negative*, so the net is not luck-inflated.

**Caveat — CLI reconciliation BLOCKED:** the optimized harness (cached taker baseline + in-memory/maker-filtered ledger) was not fully proven against the production CLI path. The exact `replay --maker-eval` reconciliation could not complete — see Known Issues #1. The verdict is robust regardless (the fee floor is arithmetic; "both lose" is independently established), but exact harness-vs-production equality is unverified.

---

## 4. Prior bot series (MoneyGrabber) — assessed, not usable

The `../../2_million_dollar_in_1_year/` MoneyGrabber V1–V5 + `mg` series (independently reviewed by Claude's 4-agent sweep and by opencode) is a MEXC **new-token launch sniper**: scrape the public listing calendar → tiered limit buys at launch → ride the pump. Verdict: **no usable edge, no profit evidence, nothing reusable.**
- Directional pump-chasing — the same category rapana already falsified, never tested honestly (its backtester runs on synthetic random data with look-ahead).
- Aggressive taker behavior — the opposite of rapana's posture, and a pattern MEXC ToS flags for **account freeze**.
- `bot_state.json` shows zero trades (paper mode); "$2M in 1 year" is only the folder name.
- **Security:** plaintext MEXC API key + secret and a Telegram bot token are committed in those configs — **rotate/revoke both.**

---

## 5. Why live remains parked

There is no validated positive-expectancy strategy to deploy. Trading the (dead) directional signals is a managed loss; maker execution only reduces that loss; idle-yield is capital-parking, not trading. The elaborate live-safety stack (LiveGuard, cycle-stamped clientOrderIds, reconcile contract, preflight gates) is sound and is prerequisite insurance — but it has no profitable strategy to guard, so live stays off. As an extra safety fact: the live executor is **not even wired into the CLI run paths today** — `run-fleet` and `paper-run` build `PaperExecutor` regardless of `RAPANA_ENV`, so real orders cannot be placed without deliberate manual wiring. The only live-touching commands are read-only (`live-check` preflight, `status` balance read, `ingest` data fetch).

---

## 6. Known issues (for any future restart)

1. **`DecisionLedger.append` is O(n²)** — it tail-scans the JSONL ledger on every append (digest/dedup). On a full-year backtest the taker ledger reached ~47 MB / ~147k lines and the production `replay --maker-eval` CLI did not finish the taker baseline in ~64 min. This blocks exact long-horizon CLI backtests/reconciliation and must be fixed (indexed/streamed digest, not a tail re-scan) before trusting the production path at scale.
2. Maker fill model is optimistic (strict-penetration fills at limit, no queue position, no adverse selection, binary fills) — fine for a cost-layer estimate, not for a live MM edge claim.

---

## 7. What a real restart would require

Halting is "for now," not "delete the work." A genuine money-making attempt would need a **paid information advantage** (free data is exhausted), not another free-data strategy:

- **Order-flow / L2 microstructure** (shelved future probe, human-reauthorized only). First deliverable must be a **feasibility memo + tiny data sample** — can we legally and reliably capture MEXC trades/L2, replay them, model fees/queue/adverse-selection, and define a DSR/drift gate? — **not** a strategy build, no profit claim. Note: real microstructure edge lives at sub-second timescales that 1h/REST infra and MEXC ToS may not support.
- **On-chain flows** or **news/social NLP** — heavier data builds; the one place an LLM genuinely adds value (reasoning over novel text, not recombining price).
- Better execution infra (lower latency) if any execution-sensitive edge is pursued.

---

## 8. Bottom line

rapana did its job: it searched the accessible edge space rigorously and **refused to lie about an edge it doesn't have.** It saved real capital by falsifying six-plus tempting strategies and an entire launch-sniper bot. It found exactly one durable positive — a ~1.7%/yr maker fee saving — which reduces the cost of trading but does not, on its own, make money. Becoming a profitable *trader* requires a deliberate new investment in a paid information edge and better infrastructure. Until then: **halted, documented, live parked.**
