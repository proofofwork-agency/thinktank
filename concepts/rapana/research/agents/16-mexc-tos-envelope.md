# 16 — MEXC ToS / Anti-Bot Policy & the Safe Operating Envelope

**Agent:** 16/60 · **Scope:** MEXC anti-bot / anti-HFT / anti-arbitrage policy boundary
**Goal:** Establish the *Safe Operating Envelope* every rapana strategy must satisfy to avoid account freeze / clawback / rollback.
**Status:** Load-bearing — this is the **rule, not a suggestion**. All other strategy agents must respect §5 (Envelope) or flag an exception.

---

## 0. TL;DR (the envelope, in 4 lines)

> **Spot-only, maker-limit, ≤1 order / symbol / 60 s, cancel ratio ≤30%, min 30 s between create→cancel, no cross-account or cross-venue hedging, no event-concentrated bursts, no sub-second anything, manual-looking cadence.** No futures auto-trading (KYB-gated). No triangular / spatial / latency / funding arb. Sweep profits; keep only working margin on-exchange.

---

## 1. Primary sources (read these first)

| # | Source | URL | Date |
|---|---|---|---|
| S1 | **MEXC "Why MEXC Restricts Automated Trading"** (the policy article) | https://www.mexc.com/support/article/why-mexc-restricts-automated-trading-17827791531135 | updated **2026-05-26** |
| S2 | **MEXC Risk Control Guideline** (the load-bearing legal text, incorporated into ToS) | https://www.mexc.com/announcements/article/mexc-risk-control-guideline-17827791524314 | May 2025, **last updated Apr 2026** |
| S3 | **MEXC User Agreement / Terms of Service** (Clauses 9, 17, 19, 21) | https://www.mexc.com/terms | Last Updated 2025-05-29 |
| S4 | **AFM consumer warning on MEXC** (unlicensed in NL/EU) | https://www.afm.nl/en/sector/actueel/2025/sep/mr-mexc-waarschuwing | 2025-09-24 |
| S5 | Internal synthesis — `RESEARCH-SYNTHESIS.md` §3 (Risk 2) | repo root | 2026-06-23 |

S1–S3 were **re-fetched and verified live for this report**; the Risk Control Guideline (S2) is the single most important document — it is the legal text MEXC enforces against.

---

## 2. What MEXC actually restricts (verbatim from primary sources)

The policy is **behavioral/pattern-based, not threshold-based.** MEXC publishes **no numeric thresholds** (no "N orders/min", no "cancel ratio > X%"). Detection is at MEXC's **"absolute sole discretion"** (S2 §7.2, S3 Clause 9, 18, 21). Treat any published number as marketing, not protection.

### 2.1 Explicitly named prohibited patterns (Risk Control Guideline §5)

| Code | Prohibited pattern | Rapana exposure |
|---|---|---|
| §5.2.1 | **Unauthorized automated/programmed methods** — tools, scripts, deep linking, bots, spiders to place/execute orders | **HIGH** — every rapana strategy is a script |
| §5.2.2 | Abnormal devices / networks / IPs / device fingerprints concealing identity or activity | MED — IP-whitelist key is fine; **VPN/proxy/rotation is not** |
| §5.2.3 | Scanning/probing undocumented APIs, hidden endpoints | LOW — we use documented ccxt only |
| §5.2.4 | Non-standard protocol sequences, evading detection | LOW |
| §5.2.5 | Masquerading as multiple clients, faking device IDs / user-agents / sessions | LOW (don't spoof) |
| §5.2.6 | **Submitting & cancelling large volumes of orders** — spoofing, **quote-stuffing, order-bombing** | **HIGH** — naive grid/MM trips this |
| §5.2.7 | Coordinated proxies / VPNs / distributed networks to split limits | LOW — single IP |
| §5.3.1 | **Pump/dump, wash trading, self-trading, front-running, quote stuffing, spoofing, layering, coordinated transactions across related accounts** | MED — wash/self-trade risk in any 2-account layout |
| §5.5 | **Position-limit evasion** — splitting across accounts/sub-accounts/3rd parties to aggregate exposure | **HIGH** if we ever run multiple MEXC accounts |
| §5.6.1 | **Frequent order placement & cancellation, synchronized execution, repetitive short-duration trades** that distort normal market activity | **HIGH** — the single biggest trap for any active strategy |
| §5.6.2 | **Hedging, cross-market arbitrage, strategies exploiting rule discrepancies / system loopholes / pricing gaps / latency differences / abnormal liquidity**; trading concentrated around **predictable price gaps (open/close, session transitions), news events, low-liquidity periods**; **simultaneous long+short forming locked/hedged exposures without genuine market risk** | **FATAL** — kills the entire "arbitrageur / funding-rate-arb / triangular / cross-venue" strategy class outright |
| §5.6.3 | Multi-account / sub-account / 3rd-party to bypass rules, limits, position caps; technical/network/infra advantage for executions under non-standard conditions | **FATAL** for any multi-venue or low-latency edge |
| S3 Cl.9(f), 17(c), 19(o) | Pump/dump, wash, self-trading, front-running, **quote stuffing, spoofing, layering**, insider trading, market manipulation | duplicate-confirm |

### 2.2 What "enforcement" actually looks like (S2 §6, §7)

- **Detection → immediate account freeze** (no prior notice; S1 §2, S3 Cl.9, 21).
- **30-day enhanced monitoring** (S2 §7.3.1) for first/suspicious cases — MEXC watches for new-account/associated-account evasion.
- **Up to 180-day restriction** (S2 §7.3.2) for coordinated or high-risk violations.
- **Transaction rollbacks / profit disgorgement** (S2 §7.3.3) — MEXC can reverse fills and claw profits, not just freeze.
- **Permanent exclusion + asset forfeiture** (S2 §7.3(e)) for severe cases.
- **First-offense leniency** (S1 §2): users who violated "due to a lack of understanding," were *not* engaged in **malicious arbitrage**, and caused **no significant market impact** may be restored after acknowledging the rules. → This is the single most important sentence for rapana: **be small, slow, non-arb, and clearly behavioral — not predatory.**
- **No internal-detail disclosure**: MEXC refuses to share what specifically triggered a flag (S2 §7.4.5). You will not get a precise reason. Stay far inside the line.

### 2.3 Futures are stricter than spot

- **Futures API auto-trading is institution-only (KYB).** S1 §4 is explicit: *"API access applications are primarily available to institutional users"* — KYB + qualification review + `institution@mexc.com`. S2 §4.2 lists *"Suspected automated trading activities conducted without proper authorization"* as a top futures trigger.
- Futures API was reopened only **2026-03-31** after a ~3.5-year institutional-only closure (`RESEARCH-SYNTHESIS.md:54`).
- **Rapana retail sleeve = spot-only for the foreseeable future.** Any futures path is a Phase-2 KYB conversation with the human + MEXC, not a bot decision.

---

## 3. What is clearly ALLOWED for retail (the safe zone)

MEXC's framing (S1 §3, §5) is *protecting retail / event fairness from predatory HFT-arb*, not banning all API use. The pattern that survives:

| Allowed posture | Why it's safe | Source |
|---|---|---|
| **KYC'd personal account, single identity, single IP** | Baseline identity hygiene; no §5.2.2 / §5.2.5 / §5.2.7 trigger | S1 §2, S3 Cl.4 |
| **Low-frequency, manual-style API trading** | Doesn't match §5.2.6 / §5.6.1 "frequent"/"short-duration" patterns | S1 §5 ("open to bot trading") |
| **Maker limit orders, post-only** | Adds liquidity (the *opposite* of spoofing/quote-stuffing); aligns with MEXC's 0% maker fee intent | S1 §1, S3 Cl.13(b) |
| **DCA, scheduled rebalancing, occasional event trades** | Sparse, scheduled, low-volume — doesn't "distort normal market activity" | S2 §5.6.1 inverted |
| **Single-account exposure within stated position limits** | No §5.5 / §5.6.3 violation | S2 §5.5 |
| **Directional trades that carry genuine market risk** | Avoids §5.6.2 "locked/hedged exposure without genuine market risk" | S2 §5.6.2 |
| **Read-only market data scraping at polite rates** | Documented API, normal polling — does not "place or execute orders" | S2 §5.2.1 scope |

The MEXC "first-offense leniency" clause (S1 §2) is the Rosetta Stone: a retail user who is **small, slow, non-arbitrage, non-impact** is the user MEXC wants to keep. Rapana must look exactly like that user.

---

## 4. 2025-2026 enforcement evidence

| Case | Detail | Source |
|---|---|---|
| **MEXC's own published case study** (S2 §8) | **2025-05-30 03:06:18 UTC**: multiple associated accounts from **identical IPs** entered **FLOCKUSDT** futures at **synchronized timing**, identical entry prices, combined ≈**50% of pair volume** → flagged as position-limit evasion / manipulation → **restricted + 30-day observation** on 2025-05-31. | S2 §8 (primary, MEXC-authored) |
| **AFM public consumer warning** (2025-09-24) | AFM: MEXC offers in NL **without MiCAR license**, illegally targets Dutch consumers (X campaigns, conference sponsorship); entity location unclear. MiCAR in force 2024-12-30; **full MiCA enforcement 2026-07-01** (~1 week from now). → legal-access risk, not a freeze, but a *jurisdictional* freeze/exit risk. | S4 |
| **Futures API ~3.5-yr institutional-only closure, reopened 2026-03-31** | Retail futures auto-trading was structurally unavailable; MEXC retains KYB gate. Any "futures bot" plan from 2022–Q1-2026 was non-viable. | RESEARCH-SYNTHESIS.md:54 |
| **"1,500-account freeze" / "$3M White Whale freeze + apology"** | Color only — single non-primary reposts. **Do not load-bearing these numbers.** The verified primary policy + AFM warning + S2 case study carry the risk argument on their own. | RESEARCH-SYNTHESIS.md:59 (calibration note) |
| **Pattern: "Why MEXC Restricts Automated Trading" article re-updated 2026-05-26** | Active policy maintenance — MEXC is iterating the enforcement framing in real time. Expect tightening around 0-Fee events (S1 §3 explicitly cites 0-Fee Fest arb exploitation). | S1 (date stamp) |

**Reading:** MEXC is not a passive venue — it actively publishes enforcement case studies and revises the guideline on a ~6–12 month cadence. Any envelope we set must assume the *next* tightening, not just today's text.

---

## 5. THE SAFE OPERATING ENVELOPE (rapana-wide rule)

Every rapana strategy, executor, and backtest must satisfy **all** rows below. A strategy that violates any row is **rejected at design review**, regardless of backtest P&L. The envelope is intentionally conservative because MEXC discloses no numeric thresholds — we leave a wide margin from any pattern MEXC names as suspicious.

### 5.1 Hard envelope table

| Dimension | Limit / Rule | Rationale (which § it avoids) |
|---|---|---|
| **Market** | **Spot only.** No futures/perp auto-trading without KYB + human approval. | S1 §4, S2 §4.2 |
| **Order type** | **`postOnly` limit orders** only (maker). Market orders only for explicit risk-close (kill-switch flatten). | §5.3, S1 §1 (maker-favorable) |
| **Order rate** | **≤ 1 new order per symbol per 60 s**, global cap **≤ 30 orders/hour** across all symbols. | §5.2.6, §5.6.1 (anti "frequent placement") |
| **Cancel ratio** | **≤ 30% cancel ratio** (cancels / (cancels + fills)) measured on rolling 24h. | §5.2.6 (anti "quote-stuffing") |
| **Min create→cancel spacing** | **≥ 30 s** between order creation and any cancel. No instant cancel cycles. | §5.6.1 (anti "short-duration") |
| **Min trade spacing** | **≥ 60 s** between *executed* trades on the same symbol; ≥ 5 min between rounds of a strategy. | §5.6.1 (anti "repetitive short-duration") |
| **Burst ban** | **No >3 orders in any 10 s window** anywhere. No sub-second activity of any kind. | §5.2.6, §5.6.1 |
| **Event blackouts** | **No new orders in the ±5 min around**: scheduled listings, 0-Fee events, funding settlements, UTC 00:00 rollover, major macro news windows. | §5.6.2 (anti "predictable gap" / "news event" concentration) |
| **Arbitrage — ALL forms** | **PROHIBITED**: triangular, spatial/cross-venue, latency, funding-rate, basis, self-trade, wash. | §5.6.2, §5.3.1, S3 Cl.19(o) |
| **Hedging / market-neutral** | **PROHIBITED** if it forms locked/symmetric exposure "without genuine market risk." Directional only; if hedging, expose one leg only. | §5.6.2 |
| **Accounts** | **One MEXC account, one identity, one IP.** No multi-account, no sub-account splitting, no shared credentials across sleeves. | §5.5, §5.6.3, §5.2.5 |
| **Network** | Static IP, no VPN/proxy rotation, no device-id spoofing. Documented ccxt endpoints only. | §5.2.2, §5.2.3, §5.2.7 |
| **Position / volume share** | **Never >2% of a symbol's 24h volume**; never approach position limits. Hard cap on small-cap alts (higher MM sensitivity). | §5.5, §8 case study (50% share = flagged) |
| **Cadence pattern** | Jittered, human-like inter-trade intervals (±30% randomization on scheduled cadence). No metronomic regularity. | §5.6.1 (anti "synchronized") |
| **Strategies permitted** | **Tier A only**: DCA, scheduled rebalance, conservative stablecoin yield, occasional directional event trade. Grid/MM/arb = deferred to post-KYB or off-MEXC. | RESEARCH-SYNTHESIS.md:71-75 |
| **Risk controls** | Per-trade ≤1% capital risk; daily-loss kill ~3–5%; total-DD kill ~15–20% → auto-flatten + halt + human re-arm. Idempotent client order IDs; query-before-retry. | RESEARCH-SYNTHESIS.md:77 |
| **Custody** | Working margin only on-exchange; sweep profits to self-custody on schedule. Withdraw-disabled, IP-whitelisted, pair-scoped keys. | RESEARCH-SYNTHESIS.md:55 |

### 5.2 Operational corollaries (must-hold for any agent that places orders)

1. **Cancel discipline.** Any strategy that needs to *churn* orders (grid re-pricing, MM quote refresh) is **not allowed on MEXC** in the retail sleeve. The cancel-ratio cap (≤30%) makes classic grid/MM structurally impossible — that is by design.
2. **No "always-on" quoting.** Maker orders must represent *genuine intent to take the position*, sit for a meaningful time, and either fill or be cancelled once — never refreshed in a loop.
3. **Single-client pattern.** Rapana speaks to MEXC from one process, one IP, one key. The "fleet" is *internal* (advisory + risk gate); only **one** order path touches the exchange.
4. **Event-aware scheduler.** The executor must hard-block order placement during event blackout windows (§5.1) regardless of strategy signal.
5. **Auditability.** Log every order/cancel with intent, timestamp, and which envelope rule authorized it. If MEXC ever does flag us, a clean human-style audit trail is the only viable appeal artifact (S2 §7.4.1).
6. **Futures = separate conversation.** Any futures strategy is gated behind: (a) human approval, (b) KYB / institutional authorization via `institution@mexc.com`, (c) a separate Contract credential set. No exceptions from the bot layer.

---

## 6. How other agents must use this

- **Strategy agents (01, 02, 03, 06, 07, etc.):** your design must pass §5.1 row-by-row. If it can't, propose a Phase-2 / off-MEXC venue, do not weaken the envelope.
- **Executor / client agents (08):** enforce §5.1 at the order-path level (rate limiter, cancel-ratio meter, event-blackout calendar, post-only flag). The envelope is a **code contract**, not a doc.
- **Risk-gate (03):** treat any envelope breach as a **halt condition** equal to drawdown breach.
- **LLM/fleet agents (05):** the LLM is fenced outside the order path (`RESEARCH-SYNTHESIS.md:65`); this envelope applies to whatever *does* place orders.

---

## 7. Open risks / things this envelope does NOT protect against

- **No published thresholds** → envelope is a conservative guess. MEXC can flag behavior inside our limits at its sole discretion (S2 §7.2).
- **MiCA 2026-07-01** → EU access may be interrupted irrespective of trading behavior (S4). Legal gate, not trading gate.
- **Custody / deplatforming** → even a "safe" account can be frozen for AML/tainted-coin reasons unrelated to order pattern. Sweep discipline is the only mitigation.
- **0-Fee events** → MEXC explicitly flags arb exploit during these (S1 §3). We must *trade less* during them, not more.
- **Calibration of the "≤2% volume share"** — that's a conservative internal choice; for illiquid alts even 2% may be too high. Tighten per-symbol in the universe selector.

---

## 8. Sources cited (consolidated)

- S1 — MEXC, "Why MEXC Restricts Automated Trading," updated 2026-05-26. https://www.mexc.com/support/article/why-mexc-restricts-automated-trading-17827791531135
- S2 — MEXC, "Risk Control Guideline," May 2025, last updated Apr 2026. https://www.mexc.com/announcements/article/mexc-risk-control-guideline-17827791524314
- S3 — MEXC, "User Agreement / Terms of Service," 2025-05-29. https://www.mexc.com/terms
- S4 — AFM, "AFM warns consumers against crypto platform MEXC," 2025-09-24. https://www.afm.nl/en/sector/actueel/2025/sep/mr-mexc-waarschuwing
- S5 — `RESEARCH-SYNTHESIS.md` §3 Risk 2 (repo root, 2026-06-23).
