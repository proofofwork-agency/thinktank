# Rapana — Risk-Fenced MEXC Research Fleet

**Location:** `thinktank/concepts/rapana`  
Risk-fenced, **paper-first, audit-first** multi-agent trading system for MEXC (spot).

> **Status (honest):** free-data directional alpha is **falsified**. Live trading is **PARKED**.  
> Rapana’s unique product is the **honesty gate + risk rails + research ledger**, not an LLM daytrader.  
> See `RESEARCH-CLOSURE.md`, `state/evolve/WHY_NOT_MATCH_AI_BOTS.md`, `state/evolve/COUNCIL_VERDICT.md`.

> **Reality check:** autonomous LLM trading alpha is unproven. This fleet proposes, debates, and
> risk-gates trades — it does *not* get free rein over your funds. Withdraw is disabled at the API
> level; a kill switch and circuit breakers are load-bearing.

---

## Where it sits in thinktank

Sibling concepts under `thinktank/concepts/`:

| Concept | Role |
|---------|------|
| **[rapana](./)** (this repo) | MEXC paper fleet, quant falsification, risk fences; live **PARKED** |
| **[iro](../iro/)** | Eyes · Search · Run — closed-loop intelligence architecture (POMDP prototype); not trading |
| **[ultrabrain](../ultrabrain/)** | Verifier-grounded scientific coder (propose → verify); not trading |
| **[actweave](../actweave/)** | Record / replay / drift of agent tool-loops |
| **[cog](../cog/)** | Capability-indexed measurement / settlement rails |
| **[deliveryproof](../deliveryproof/)**, **[vouch](../vouch/)** | Verify-gated delivery / surety |
| **[sealedtrial](../sealedtrial/)**, **[sol](../sol/)** | Evaluation integrity / related concept stubs |

**Vs IRO:** IRO invents non-orthodox perception/search/run for agents. Rapana is a **venue-specific research fleet** with honest markets gates. They share a *fail-closed* culture, not a code path.

**Vs UltraBrain:** UB gates code/math proposers. Rapana gates **trades** with deterministic risk. Neither is an LLM daytrader.

Rapana is a **lab / loss-prevention system**, not a free-data money printer.

---

## What it is good at (unique)

| Strength | Notes |
|----------|--------|
| **Honest validation** | Walk-forward, holdout, Deflated Sharpe, drift/random-entry bars |
| **Deterministic risk** | Kill switch, circuit breaker, pre-trade checks LLMs cannot override |
| **Paper multi-agent fleet** | Analysts → debate → risk → PM → paper execution |
| **Audit journal** | Hash-chained, replay-verifiable decisions |
| **Falsification record** | Documented NO-GOs (TA, funding, unlocks, snipers, …) |

**Not good at:** free-data price prediction, matching arxiv/SaaS “AI bot” marketing returns.

---

## Research status

| Track | Result |
|-------|--------|
| Free-data directional strategies | **FAIL** (honest DSR gates) |
| Funding carry / spike / unlocks | **FAIL** |
| Maker execution | **Cost layer only** (reduces bleed; not alpha) |
| BNB trend / F&G avoid_greed | Practical holdout survivors; **not** hard DSR pass |
| Live capital | **PARKED** (no positive-expectancy strategy to deploy) |

**Forward paths (council):** eligibility + defense overlays + idle Earn dry-run + Kickstarter **notify-only** — not free-data TA restarts.  
See `state/evolve/MISSED_ALTERNATIVES.md` and `state/evolve/COUNCIL_VERDICT.md`.

---

## Status (build)

**Phases 0–3 built (paper path).** MEXC read client, ingestion, decision ledger, risk guardrails;
analyst agents, strategies, backtest engine; fleet orchestrator + paper + replay; live path exists
behind preflight but is **not** the supported mode until an edge clears the bar.

**Branch context:** structural / research work (e.g. `sprint-1-structural-value`); micro budget
profile: `state/micro_50.env`.

---

## CLI

```
rapana status          # connectivity + config + balances
rapana ingest          # pull OHLCV for watched symbols
rapana backtest --symbol BTC/USDT --strategy trend
rapana replay --limit 1000     # full-fleet replay (no money)
rapana run-fleet      # one decision cycle (paper)
rapana paper-run      # scheduled paper daemon
rapana evolve         # pre-registered research loop (DSR-gated)
rapana check-trade ...         # dry-run through risk gate
rapana live-check     # preflight only (no order)
rapana promote / demote        # staged capital (human gate; live parked)
rapana journal-verify
rapana notify-test
```

---

## Quick start

```bash
cd thinktank/concepts/rapana
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # READ-ONLY MEXC key (NO withdraw), bind IP
rapana status
rapana ingest
rapana backtest --symbol BTC/USDT --strategy trend --timeframe 1h
rapana replay --limit 1000
rapana paper-run --once
pytest && ruff check .
```

Optional micro profile (hard capital ceiling):

```bash
# review then merge carefully — do not clobber secrets
# cat state/micro_50.env >> .env
```

---

## Layout

```
rapana/                 # Python package
  config.py             # env settings (incl. RAPANA_CAPITAL_BUDGET_USD)
  mexc/client.py        # CCXT MEXC wrapper
  data/                 # SQLite OHLCV / funding / macro store
  journal/ledger.py     # hash-chained audit journal
  risk/                 # KillSwitch, CircuitBreaker, PreTradeChecker, live safety
  fleet/                # orchestrator, paper/live execution, maker model
  agents/               # multi-role analysts + brain
  backtest/             # engine, DSR validation, carry / XS / unlocks
  strategies/           # rule-based cores
  research/evolve/      # self-evolving research loop
  cli.py
tests/
research/agents/        # 60-agent research notes
state/evolve/           # hunt results, council verdict, edge notes
RESEARCH-CLOSURE.md     # alpha-hunt halt (authoritative)
PLAN.md                 # architecture + roadmap
```

---

## Guardrails (non-negotiable)

- **MEXC key: no withdraw.** Prefer read-only + IP bind for research; trade keys only with human go.
- **Kill switch:** `touch state/KILL_SWITCH` halts the fleet.
- **Circuit breaker:** daily loss / drawdown policy.
- **Pre-trade gate:** deterministic — notional, price band, exposure, throughput.
- **Capital budget:** `RAPANA_CAPITAL_BUDGET_USD` clamps max order size (e.g. 50 → max ~$47.50).
- **Audit journal:** hash-chained signals / proposals / fills.

---

## Roadmap (post-closure)

1. **Do not** restart free-data directional / LLM daytrade hunts.  
2. Defense overlays (delist / calendar / depeg) — fail-closed.  
3. Idle Earn dry-run after product terms.  
4. Kickstarter **notify-only** (no auto listing-window sells).  
5. Maker post-only as **cost default**, never alpha claim.  
6. Live remains **PARKED** until exchange-reconciled edge clears honest gates.

Historical phases (built): foundation → signals/backtest → paper fleet → gated live prep.

---

## Disclaimer

Not financial advice. Crypto trading can lose 100% of capital.  
Paper thoroughly. Do not run live on unvalidated free-data “edges.”
