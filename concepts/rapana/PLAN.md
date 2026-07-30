# RAPANA — Agent-Managed MEXC Trading Fleet
## Research Synthesis + Implementation Plan

---

## TL;DR — The Honest Reality (read this first)

The "time of agents" is real for **infrastructure** (agent wallets, payments, on-chain execution — Coinbase AgentKit, x402, Virtuals, elizaOS). It is **NOT proven** for "LLM autonomously grows your crypto portfolio for profit." Every credible source confirms:

- Profitable autonomous trading today = **deterministic bots** (arbitrage/MEV/market-making), **not LLM agents**.
- There is **no audited evidence** an LLM agent beats buy-and-hold or quant baselines.
- LLMs hallucinate + crypto is irreversible = catastrophic risk if ungated.

**Therefore the plan is NOT "let an agent loose on your funds." It is "build a risk-fenced fleet that proposes, debates, risk-checks, and executes — with you (or hard policy gates) as the final authority, starting on paper with tiny staged capital."**

---

## 1. What We're Building

A **multi-agent trading fleet** on MEXC that watches trends, analyzes the market, debates trades, risk-gates them, and executes — with full audit trail, kill switch, and staged capital deployment. You stay in control of the big decisions; the fleet does the watching and the busywork you don't have time for.

### Recommended Stack (open-source, MEXC-native)
| Layer | Choice | Why |
|---|---|---|
| **Execution / venue** | **Hummingbot** (native MEXC spot connector) **or** **CCXT `mexc`** directly | Only mature framework with maintained MEXC connector; Hummingbot MCP bridges to agents |
| **Agent orchestration** | **LangGraph** | Durable (survives crashes), interruptible (human approvals), persistent memory — built for long-running trading loops |
| **Decision pattern** | **TradingAgents topology** (Analysts → Bull/Bear debate → Risk → Portfolio Mgr → Trader) | Best-fitting skeleton from literature (arXiv 2412.20138) |
| **Market data** | **CCXT** + CoinGecko/Santiment/Glassnode | CCXT covers MEXC data+execution; others add sentiment/on-chain |
| **Fastest alternative** | **OctoBot** (MEXC via CCXT + built-in OpenAI/Ollama mode) | If you want low-effort all-in-one |
| **Avoid** | AutoGen (maintenance mode), OpenAI Swarm (superseded), Zenbot (archived) | |

### MEXC API Key Facts (constraints we must design around)
- **No testnet/sandbox** → all testing is live; use `POST /api/v3/order/test` (signing validated, no fill) + read-only keys.
- **No native OCO / trailing-stop** → emulate client-side (place/cancel TP/SL pairs).
- **Spot rate limits:** 500 weight / 10s per IP *and* per UID; bans escalate 2min→3 days. Use WebSocket (100 msg/s, 30 streams max) for data.
- **No public API for grid/copy bots** → those are UI-only; we build our own logic.
- **Two auth schemes** (Spot vs Contract) — don't reuse one client for the other.
- **API keys without bound IP expire in 90 days**; bind IP for production. Host in AWS Japan/Singapore for stable connectivity.

---

## 2. Fleet Design (the "30 agents" → right-sized to 12 roles)

You asked for 30 agents; research says **specialization beats headcount**. A focused fleet of 12 cooperating roles beats 30 redundant ones. Each role maps to real trading-firm functions:

```
                       ┌─────────────────────────────────────────┐
                       │         YOU (human authority)            │
                       │ Approve big trades · Kill switch ·       │
                       │ Daily digest · Set limits & policy        │
                       └──────────────────┬──────────────────────┘
                                          │  (interrupts / approvals)
        ┌─────────────────────────────────┴─────────────────────────────┐
        │              ORCHESTRATOR (LangGraph supervisor)              │
        │   registry · scheduler · checkpoint/resume · circuit-breaker  │
        └───────┬──────────┬───────────┬──────────┬─────────┬───────────┘
                │          │           │          │         │
           ┌────▼───┐ ┌────▼────┐ ┌────▼─────┐ ┌──▼──────┐ ┌▼──────────┐
           │ Market │ │ News/   │ │ Macro/   │ │Arbitrage│ │  Yield    │
           │Analyst │ │Sentiment│ │On-Chain  │ │ Scanner │ │Strategist │
           └────┬───┘ └────┬────┘ └────┬─────┘ └────┬────┘ └┬──────────┘
                └──────────┴──────┬───┴─────────────┴───────┘
                                  ▼  (shared blackboard: signals + market view)
                         ┌────────────────────┐
                         │  Bull  ◄──debate──► │  Bear Researcher
                         └─────────┬──────────┘
                                   ▼ recommended action + thesis
                              ┌─────────┐
                              │  Risk   │── hard veto / size adjust
                              │ Manager │   (limits, drawdown, leverage)
                              └────┬────┘
                                   ▼
                           ┌───────────────┐
                           │ Portfolio Mgr │── approved order
                           └───────┬───────┘
                                   ▼ (approval gate if > threshold)
                           ┌───────────────┐
                           │  Execution    │──► MEXC via Hummingbot/CCXT
                           │  Trader       │
                           └───────┬───────┘
                                   ▼ fills
                           ┌───────────────┐
                           │ Compliance/   │── immutable decision journal,
                           │ Ledger Auditor│   daily digest, replay
                           └───────────────┘
```

| # | Role | What it does |
|---|---|---|
| 1 | Market Analyst | OHLCV, order book, funding rates, technical signals (RSI/MACD/vol) |
| 2 | News/Sentiment Analyst | Headlines, X/Reddit/Discord, on-chain social → sentiment read |
| 3 | Macro/On-Chain Analyst | ETF flows, whale moves, stablecoin supply, TVL, rates/DXY |
| 4 | Arbitrageur | CEX/DEX spreads, funding basis, triangular arb scanning |
| 5 | Yield Strategist | Staking/lending/LP/delta-neutral yield evaluation |
| 6 | Bull Researcher | Builds long thesis in structured debate |
| 7 | Bear Researcher | Builds short/risk thesis in structured debate |
| 8 | Risk Manager | **Hard veto gate** — position limits, VaR, drawdown, leverage caps (deterministic, not LLM) |
| 9 | Portfolio Manager | Approves/sizes target allocation after risk review |
| 10 | Execution Trader | TWAP/VWAP/iceberg smart routing to MEXC |
| 11 | Orchestrator/Supervisor | Schedules pipeline, state, retries, circuit-breaker |
| 12 | Compliance/Ledger Auditor | Immutable per-trade journal, daily digest, replay |

The **Bull↔Bear debate** (from TradingAgents) is the core anti-bias mechanism: no trade happens without a structured adversarial pass.

---

## 3. Mandatory Guardrails (non-negotiable)

Built from real disasters (Knight Capital $440M/45min, Mt.Gox, FTX, Flash Crash):

**Secrets & keys**
- API keys in a vault (HashiCorp Vault / AWS Secrets Manager), fetched at runtime, rotated.
- **Withdraw permission DISABLED.** Read + trade only. Withdraw is a separate manual flow.
- IP-allowlist keys to the agent's static egress IP. Bind IP so they don't expire.

**Order & position controls (deterministic gates the LLM cannot override)**
- Max position size per symbol + max total exposure (≤ X% of capital).
- **Max daily loss / drawdown circuit breaker** → halts all trading, cancels open orders.
- Max orders/min + max notional/order (Knight-proofing).
- Idempotency (client order IDs) to prevent duplicate fills on retry.
- Sanity price bounds (reject quotes > N% from reference → Flash Crash-proofing).

**Custody**
- Self-custody the bulk (hardware wallet). **Minimal working balance only** on MEXC.
- Top-up workflow: time-delayed, amount-capped transfers. Never auto-drain cold storage.

**LLM-specific**
- External data (news/social/on-chain) treated as **untrusted**; isolated from the action layer.
- Hard action allow-list; agent cannot exceed a fixed schema regardless of input.
- High-impact actions require a deterministic policy gate, not model judgment.

**Operational**
- Heartbeat + watchdog: stall or exchange unreachable → auto-flatten/freeze.
- Hardware + software **kill switch** that flattens positions and revokes the key.
- Monitor PnL/exposure/errors with alerts (Telegram/Slack).

---

## 4. Phased Rollout

### Phase 0 — Foundation (Week 1–2)
- Repo scaffold, secrets vault, MEXC read-only key (IP-bound, no withdraw).
- CCXT `mexc` connector, market-data ingestion → time-series store (TimescaleDB/QuestDB).
- Hummingbot or CCXT execution layer wired (paper-trade mode first).
- Decide: **LangGraph custom build** vs **OctoBot (fast path)**.

### Phase 1 — Data + Signals + Backtest (Week 3–5)
- Build analyst agents (market/sentiment/macro). Pure read; no orders.
- Event-driven backtest engine, point-in-time correct, anti-lookahead bias.
- Backtest simple strategies (DCA, grid, trend-follow) on MEXC historical data.
- **Gate:** only proceed if backtest clears a sensible Sharpe vs buy-and-hold.

### Phase 2 — Paper Trading Fleet (Week 6–8)
- Full 12-role fleet on LangGraph, paper-trade mode (identical decision path to live).
- Bull/Bear debate + Risk Manager veto + Portfolio Manager + Execution (paper fills).
- Decision journal + daily digest. **Run ≥ 4–8 weeks.** No real money yet.
- **Gate:** paper performance + reliability must clear before any live capital.

### Phase 3 — Staged Live Capital (Week 9+)
- Deploy **1% → 5% → 25% → 100%** of allocated capital in tranches.
- All guardrails live. Withdraw disabled at API level.
- Start spot-only, low leverage. Add futures only after proven spot track record.
- **Gate:** each tranche only after prior tranche holds within drawdown limits.

### Phase 4 — Scale & Harden (ongoing)
- Add arbitrageur + yield strategist roles once core is profitable.
- Reflection loop (feed realized PnL back into decisions).
- Tune, but never remove human kill-switch or the withdraw lock.

---

## 5. Decision You Need to Make

1. **Build path:** custom LangGraph fleet (max control, more work) **vs** OctoBot fast path (quick, less bespoke)?
2. **Scope:** spot-only to start (recommended) **vs** include futures?
3. **Capital to allocate** (only what you can afford to lose — the research is unanimous: expect drawdowns).
4. **Your involvement:** daily digest review (light) vs approval-gate on every trade above a threshold (heavier, safer early on)?

---

## 6. Key Risks to Accept Before Starting

- **No proven LLM-trading alpha.** This may underperform buy-and-hold. Treat it as a researched experiment, not a money printer.
- **Irreversible + hallucination** = the guardrails above are load-bearing, not optional.
- **Exchange counterparty risk** (FTX precedent) → keep minimal balance on MEXC.
- **Regulatory** → MEXC is Seychelles-based, no US support; KYC enforced; check your jurisdiction. (General info, not legal advice.)

---

## Sources
- a16z *State of Crypto 2025* — a16zcrypto.com/state-of-crypto-2025
- MEXC Spot v3 API — mexcdevelop.github.io/apidocs/spot_v3_en/
- MEXC Contract v1 API — mexcdevelop.github.io/apidocs/contract_v1_en/
- MEXC official SDK — github.com/mexcdevelop/mexc-api-sdk
- CCXT — github.com/ccxt/ccxt
- Hummingbot — hummingbot.org · github.com/hummingbot/hummingbot
- OctoBot — github.com/Drakkar-Software/OctoBot
- LangGraph — langchain.com/langgraph
- TradingAgents (arXiv 2412.20138) — arxiv.org/abs/2412.20138 · github.com/TauricResearch/TradingAgents
- FinRobot (arXiv 2405.14767) · FinGPT (arXiv 2306.06031) · FinAgent (arXiv 2402.18485)
- Coinbase AgentKit — docs.cdp.coinbase.com/agentkit/docs/welcome
- Knight Capital SEC Order 34-70694 — sec.gov/litigation/admin/2013/34-70694.pdf
