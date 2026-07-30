# 38 — Structural yield (real-yield / stable-LP / airdrop farming) & the YieldSleeve

**Agent:** 38/60 · **Scope:** The honest returns of *non-trading* crypto "profit" — real-yield DeFi (fees-not-emission), stablecoin-only LP/lending, airdrop-farming ROI, and MEXC Earn/Savings vs DeFi vs self-custody — plus a concrete **YieldSleeve** design that parks rapana's non-trading balance in the safest available real yield.
**Stance:** NON-standard, low-frequency, capital-preservation. Spot-only; no arb, no leverage, no perps. This agent does **not** emit a per-symbol trading signal — it sets the **fleet-level cash benchmark** that trading alpha must beat (the `cash_return` knob already exists at `cli.py:1061,1077`) and proposes a separate idle-capital deployment path. Honors `16-mexc-tos-envelope.md` §5 (yield products are MEXC's own / read-only DeFi; no multi-account farming).

**Status of evidence:** Yield APYs are **live DefiLlama API snapshots (2026-06-23)** — the most authoritative public yield oracle, not peer-reviewed but verifiable to the cent at the cited URLs. Impermanent-loss figures are the **deterministic constant-product AMM formula** (independently recomputed). Airdrop-farming ROI is **high-variance and partly anecdotal** — flagged **[HYPOTHESIS]** where magnitudes are analyst-compiled. MEXC Earn steady-state rates are bot-gated (`HTTP 403` on the learn/savings endpoints); the promo structure is verified from the live landing page, the steady-state number is inferred from peer-CEX parity and flagged as such.

---

## 0. TL;DR (4 lines)

> The most *consistent* crypto profit is not trading alpha — it is **3–6% structural real yield on dollars** (sUSDS 3.6%, sUSDe 3.5%, BlackRock BUIDL 3.5%, Maple/Centrifuge 5–6% with credit risk; blue-chip Aave/Compound/Spark stable lending median **~2.6%**, stable+stable LP base **~0–2%** with near-zero IL). Airdrop farming is **not yield** — it is high-variance, ~70% of airdropped tokens never profit holders (agent 24), and its ROI is dominated by rare outliers, so treat it as a lottery sleeve, not a return stream. The cleanest design for rapana is a **two-sleeve split**: (A) a **Reserve sleeve** in self-custody blue-chip stable lending (~3–4%, removes CEX counterparty risk) for the long-horizon non-trading bulk, and (B) a **Trading sleeve** that keeps only the liquid buffer on MEXC — optionally swept into **MEXC Flexible Savings (~1–3% steady / 600% promo-on-capped-USDT)** — with MX-Kickstarter (agent 24 Strategy C, ~10–20% on existing MX) as a small additive carry. Crucially, this makes the **honest profit bar = ~3–4% stablecoin yield, not 0% cash** — wire it into the existing `cash_return` benchmark (`cli.py:1061`).

---

## 1. Why "structural yield" is the honest baseline rapana must beat

The fleet's entire backtest/promotion machinery (`07-profit-benchmark.md`) judges strategies against a **benchmark**. The repo already exposes the right knob: `cli.py:1061` *"benchmark return to beat (default 0 = cash; set for stablecoin yield)"*, consumed as `cash_return` in `rapana/backtest/carry.py:115` and `funding_spike.py`. **Defaulting that to 0 is the bug** — idle stables are not zero-return in 2026; they earn 3–6% in DeFi or 1–3% on MEXC Earn. Any "profitable" strategy that returns < the stablecoin yield is, in opportunity-cost terms, **losing money while bearing crypto volatility** — the definition of fake profit (agent 7's thesis).

Three structural facts make this the right baseline:
1. **It is genuinely uncorrelated to price direction.** Real-yield protocols distribute *protocol fees* (perp funding to Ethena, swap fees to Curve, borrow spread to Aave) — revenue that accrues whether ETH goes up or down. This is the only crypto return with a Sharpe profile resembling a money-market fund.
2. **It is low-frequency and free.** DefiLlama yields API (`yields.llama.fi/pools`) and MEXC Earn require no key, no KYC beyond the existing account, and fire at daily cadence — inside the §5 envelope.
3. **It is *not* arbitrage.** Earning Aave supply yield or MEXC savings interest is *not* a convergence trade; it carries real counterparty/smart-contract/depeg risk. It is therefore spot-only and envelope-safe; what it is **not** is risk-free.

---

## 2. Yield-source table (live DefiLlama snapshot, 2026-06-23)

Source for all DeFi rows: **`GET https://yields.llama.fi/pools`** (15,976 pools; filtered to TVL > $20M, stable tokens, `apyReward` ≈ 0 to isolate *real* / non-emission yield). MEXC row from the live `mexc.com/earn` landing page. **Re-run the query before any sizing** — these numbers drift with funding rates and Fed policy.

### 2.1 The load-bearing table — realistic APY, risk, URL

| # | Sleeve / source | Vehicle | Realistic APY (net) | Tail risks (honest) | Where it comes from | URL |
|---|---|---|---|---|---|---|
| **R0** | **Self-custody T-bill / fiat** | USDC → Coinbase/Brokerage T-bill | **~4.3–5.0%** | USD inflation; platform/bank risk; not on-chain | Baseline risk-free for crypto-native USD | [BlackRock BUIDL 3.53%](https://defillama.com/yields/pool/9b2d4d61-af8a-4259-b49f-cba27b32a629) |
| **R1** | **Real-yield RWA** (fees-not-emission) | BlackRock **BUIDL**, Ondo **USDY**, Invesco **USTB** | **~3.5–3.7%** | T-bill / issuer risk; tokenized fund redemption gate; smart contract | DefiLlama (base yield, no reward token) | [DefiLlama Yields](https://defillama.com/yields) |
| **R2** | **Real-yield Sky** | Sky **sUSDS** (Savings USDS) | **~3.6%** ($5.9B TVL) | DAI/USDS depeg (collateral contagion, agent 21); MakerDAO governance | MakerDAO Savings Rate, pure fee | [sUSDS pool](https://defillama.com/yields) |
| **R3** | **Real-yield delta-neutral** | Ethena **sUSDe** | **~3.5%** ($1.7B TVL); ranged **3–15%+** historically | **Funding-rate dependent** — collapses when funding flips negative (bear markets); CEX custody of hedge (USDC on Bybit/Bitfinex); UST-like perception risk | Perp funding − borrow cost | [Ethena](https://app.ethena.fi/) |
| **R4** | **Institutional credit yield** | Maple USDC/USDT, Centrifuge USDC | **~5–6%** (Maple 5.11%, Centrifuge 5.73%) | **Underwriting / loan-default risk** (Maple had ~$36M defaults in 2023 — Auros/Babel); pool manager discretion; *not* risk-free | Maple/Centrifuge pool managers lend to institutions | [Maple Finance](https://www.maple.finance/) |
| **R5** | **Blue-chip stable lending** ⭐ safest DeFi | Aave v3 / Spark **USDC·USDT·USDS** | **~2.1–3.6%** (large-pool median **2.6%**) | Smart-contract exploit (Aave never exploited at scale, but not impossible); cascade if a major collateral depegs (agent 21); **IL = none** (single-asset) | Aave supply rate = borrow rate × utilisation | [Aave](https://app.aave.com/) · [Spark](https://spark.fi/) |
| **R6** | **Stable+stable LP** (lowest IL) | Curve 3pool (DAI/USDC/USDT), Uniswap USDC-USDT | **~0–2% base** (3pool ~0.0% currently; high prints are *reward-token* emissions, not real) | Curve hack precedent (Jul 2023, **$70M**); depeg of any leg (IL only fires on *relative* depeg, agent 21 §2.3); near-zero IL in normal conditions | Swap-fee revenue | [Curve 3pool](https://curve.fi/) |
| **R7** | **Liquid staking (non-stable)** | JitoSOL 5.6%, BNSOL 5.1%, JUPSOL 5.6% (SOL); stETH ~3–4% (ETH) | **~5–6%** SOL / **~3–4%** ETH | **Not capital preservation** — exposed to SOL/ETH price (−50%+ drawdowns); slashing; LST depeg (stETH traded 0.97 in 2022) | Staking + MEV + priority fees | [Jito](https://jito.network/) |
| **R8** | **Pendle PT (fixed yield)** | sUSDe-PT, sUSDS-PT | **~6–9% fixed-term** | Counterparty to the underlying (Ethena/Sky); loss of liquidity until maturity; reward-token pricing noise | Pendle fixed-yield market | [Pendle](https://app.pendle.finance/) |
| **C1** | **MEXC Flexible Savings** ⭐ MEXC-native | USDT/USDC flexible on MEXC Earn | **~1–3% steady** (peer-CEX parity); **"up to 600% APR"** = new-user promo on capped small principal | **MEXC counterparty risk** (funds remain on-exchange — same risk as trading balance); variable rate; redeem lag on stressed days | MEXC Earn landing page (verified) | [MEXC Earn](https://www.mexc.com/earn) |
| **C2** | **MEXC Fixed / On-Chain Earn** | Fixed-term staking; on-chain delegated | **~3–15%** promo-dependent | Lock-up (early-redemption penalty per FAQ); same CEX counterparty risk while custodied | MEXC Earn FAQ | [MEXC Earn](https://www.mexc.com/earn) |
| **C3** | **MX-Kickstarter** (agent 24 §3) | Commit MX → receive new-listing tokens | **~10–20% on committed MX** | Received tokens **dump post-listing** (sell-at-open mandatory); **MX price drawdown** while committed; pool crowding dilutes | MEXC flagship retail product, ToS-safe | [Kickstarter FAQ](https://www.mexc.co/learn/article/kickstarter-event-faq/1) |
| **A1** | **Airdrop farming** (NOT yield) | Bridge/LP/transaction farming across new chains | **Expected: negative after costs; variance: huge** | ~70% of airdropped tokens never profit holders; sybil filters + clawbacks; gas/bridge capital drag; **single biggest loser: time/opportunity cost** | IntoTheBlock 23-token sample (agent 24 §2.3) | [CoinGecko: airdrop farming](https://www.coingecko.com/research/publications/airdrop-farming) |

**How to read the table:** rows R1–R5 are the **capital-preservation universe** (dollar-denominated, single-asset, no IL). R6 is dollar-denominated but carries hack risk for marginal extra yield. R7–R8 are **real yield but NOT capital preservation** (price/liquidity risk). C1–C3 are MEXC's own products (custody stays with MEXC). **A1 is not yield — it is a lottery ticket** and should never be booked as a return.

### 2.2 The two numbers worth memorising
- **Capital-preservation real yield floor: ~3–4%** (R1/R2/R5). This is the number rapana's trading alpha must clear after costs. Set `cash_return` to it (`cli.py:1061`).
- **Anything paying > ~6% on stables is either (a) emission-funded and temporary, (b) credit/underwriting risk (R4), (c) funding-rate dependent and bear-market-fragile (R3), or (d) a CEX promo on capped capital (C1).** There is no free 15% on dollars in 2026. Verify `apyBase` vs `apyReward` on DefiLlama before believing any headline.

---

## 3. Impermanent loss — the silent yield-killer (the math, independently verified)

IL is the reason "the APY looked great but I lost money." It is **deterministic**, not random, for constant-product AMMs. For a price ratio change `r = P_end / P_start`, IL = `2√r / (1+r) − 1`. Verified by direct computation (this agent):

| Price move (either direction) | Impermanent loss |
|---|---|
| 1.25× | **−0.6%** |
| 1.5× | **−2.0%** |
| 2× | **−5.7%** |
| 3× | **−13.4%** |
| 4× | **−20.0%** |
| 5× | **−25.5%** |

**Two operational consequences:**
1. **Stablecoin LPs (R6) have ~zero IL in normal conditions** (both legs are $1, so `r≈1`), but on a *relative* depeg (one stable breaks, the other holds — agent 21 §2.3) IL spikes exactly when you most want to exit. The "low-risk" label is conditional on no depeg.
2. **Concentrated liquidity (Uniswap v3) multiplies IL** — a tight range on a 2× move can lose 20–40% of principal even while earning fees. **rapana must never run a volatile-pair concentrated LP.** This is why the YieldSleeve (§6) is **single-asset stable lending only**, never an AMM position.

> Rule of thumb: if a yield requires you to hold two different assets in a pool, the "APY" is a gross figure and the net return is `APY − IL − gas`. For rapana's capital-preservation mandate, **single-asset lending (R5) dominates stable-LP (R6)** in the current regime: same order of risk, ~2–3% vs ~0–2%, and no Curve-hack exposure.

---

## 4. Airdrop-farming ROI — capital efficiency, variance, and the honest read

Airdrop farming = deliberately transacting/bridging/providing liquidity on unlaunched-token protocols to qualify for a future token drop. The mechanics are documented (CoinGecko, [What Is Airdrop Farming](https://www.coingecko.com/research/publications/airdrop-farming)): allocations scale with *fees paid, transaction count, duration, and liquidity provided* — explicitly **favoring longer/earlier participants and larger capital**, with projects actively deploying **sybil filters and clawbacks** against multi-wallet farming.

### 4.1 The economics (honest)
| Factor | Reality |
|---|---|
| **Capital efficiency** | Poor. Capital must sit in LP/bridges for *months* (zkSync, LayerZero, Wormhole farmed over 12–20 months) earning sub-market yield while waiting. |
| **Variance** | Enormous. Expected value is dragged down because **~70% of airdropped tokens never profit holders** (IntoTheBlock 23-token sample, agent 24 §2.3). The median farmer nets little; the return is carried by **rare outliers** (Hyperliquid, early Solana, Jito). |
| **Costs** | Gas (L1 bridging), bridge fees, MEV, *and* the opportunity cost of not being in the 3–4% real-yield baseline. A "farm and hold stables" strategy still pays these drags. |
| **Sybil risk** | Projects (LayerZero, zkSync) retroactively disqualified wallets with linked funding patterns; legitimate single-wallet farmers were caught in false-positive sweeps. |
| **Token risk** | Even a "successful" airdrop delivers tokens with **zero cost basis to recipients → scheduled post-claim dump** (agent 24: 50–85% sold in week 1, −20 to −40% in weeks 1–4). Realized value ≪ nominal airdrop value unless sold at listing open. |

### 4.2 The "farm and hold stablecoins, get airdrops" strategy — verdict
**Do not book this as a return stream for rapana's reserve.** It is a **convexity sleeve** (small capped allocation to asymmetric upside), not yield. If pursued at all:
- **Size it as a lottery ticket** (≤1–2% of equity, money you expect to mostly lose).
- **Use genuinely idle stablecoin LP** (R6) as the farming vehicle so the *carry* is real-yield-adjacent and the airdrop is pure upside optionality.
- **Single wallet, genuine activity** — never multi-wallet sybiling (trips both project clawbacks *and* MEXC §5.1 one-identity rule, `16-mexc-tos-envelope.md`).
- **Sell-at-listing-open discipline is mandatory** (same rule as MX-Kickstarter, agent 24 §3.2) — holding the received token converts the windfall into the −20–70% post-claim drift.

> Net: airdrop farming is **orthogonal** to the YieldSleeve. The YieldSleeve is capital preservation; airdrop farming is speculation. Keep them in separate mental accounts.

---

## 5. MEXC Earn vs DeFi vs self-custody — where is the bulk safest?

The three custodial regimes for the non-trading balance, ranked by **(safety, then yield)**:

| Custody | Mechanism | Yield | Counterparty / tail risk | Verdict for the bulk |
|---|---|---|---|---|
| **Self-custody DeFi** (Aave/Spark/sUSDS) | Your wallet → smart contract. You hold the keys. | ~2.6–3.6% | Smart-contract exploit; depeg cascade (agent 21) | ⭐ **Safest for the long-horizon reserve** — removes CEX-failure risk entirely |
| **MEXC Earn / Savings** | Funds stay on MEXC; MEXC lends/stakes on your behalf | ~1–3% steady; promos higher on capped capital | **MEXC insolvency/hot-wallet hack** — *same* risk as the trading balance; redeem lag under stress | Best for the **liquid trading buffer** that must re-enter spot quickly; do not over-concentrate |
| **On-chain / fixed staking via MEXC** | Lock-up term; principal returned at maturity | ~3–15% promo | MEXC custody + illiquidity during term | Avoid for the reserve; acceptable for a small known-horizon slice |

**The key insight: MEXC Earn does NOT reduce counterparty risk versus leaving USDT on the spot balance** — both are claims on MEXC. Earn only adds yield (and a redeem lag). Therefore:

- **For capital the fleet might trade in <24h:** leave liquid on spot, or use MEXC Flexible Savings for marginal carry (C1). Counterparty is MEXC either way.
- **For capital earmarked as long-horizon reserve (the "non-trading bulk"):** withdraw to self-custody and place in **R5 blue-chip stable lending (Aave/Spark/sUSDS)**. This is the *only* option that removes the single largest tail risk — MEXC itself. The historical crypto graveyard (FTX, Mt.Gox, Celsius) is a custody story, not a yield story.

This is the structural argument for the **two-sleeve split** in §6.

---

## 6. Proposed YieldSleeve design for rapana (with realistic numbers)

### 6.1 Concept
Split total equity into two **separate capital pools**, governed independently. The trading fleet only ever sees the Trading sleeve; the Reserve sleeve is a slow, human-supervised allocation that earns the honest baseline and removes CEX counterparty risk from the bulk.

```
            ┌──────────────────── rapana total equity ────────────────────┐
            │                                                              │
            │   RESERVE SLEEVE (capital preservation)        ~60–80%       │
            │   self-custody → Aave/Spark sUSDS  ~3–4%                     │
            │   goal: beat 0% / survive MEXC failure / fund drawdowns      │
            │                                                              │
            │   TRADING SLEEVE (the fleet, StagedCapital)     ~20–40%      │
            │   liquid on MEXC spot, staged 1%→5%→25%→100%                 │
            │   idle quote buffer → MEXC Flexible Savings ~1–3% (optional) │
            │   goal: generate alpha > 3–4% benchmark                       │
            │                                                              │
            │   CARRY SLEEVE (additive, optional)            ~0–5%         │
            │   MX-Kickstarter (agent 24 §3) on existing MX   ~10–20%      │
            │   airdrop-farm lottery (§4)                    ≤1–2%         │
            └──────────────────────────────────────────────────────────────┘
```

### 6.2 Realistic numbers (blended sleeve example, $100k equity)

| Sleeve | Allocation | Vehicle | Net APY | $/yr | Notes |
|---|---|---|---|---|---|
| Reserve | $70,000 (70%) | self-custody sUSDS / Aave USDC | **3.6%** | **+$2,520** | Removes MEXC risk from the bulk; redeemable in hours |
| Trading (deployed) | $20,000 (20%) | MEXC spot, staged | strategy α | — | Must beat 3.6% after fees or it is fake profit |
| Trading (idle buffer) | $8,000 (8%) | MEXC Flexible USDT | **~2%** | **+$160** | Counterparty = MEXC (same as spot); marginal carry |
| Carry — Kickstarter | $1,500 in MX (1.5%) | commit MX (not frozen) | **~12%** | **+$180** | Sell-at-open mandatory; MX is a separate position |
| Lottery — airdrop farm | $500 (0.5%) | idle stable LP on new chain | n/a | **high variance** | Booked as $0 expected; pure optionality |
| **Total sleeve yield** | | | | **≈ +$2,860 / yr ≈ 2.9% blended** | **Floor that trading alpha must beat** |

**The honest headline: a well-run YieldSleeve earns ~2.5–3.5% blended on total equity with near-zero directional risk and *reduced* counterparty concentration.** The trading sleeve must add alpha *on top of* this to justify its existence; if a 12-month live run shows trading P&L net of costs < ~3%, the honest conclusion is "shut the trading sleeve down and move everything to the Reserve sleeve."

### 6.3 ToS / envelope check (`16-mexc-tos-envelope.md` §5)

| Sleeve | Envelope row | Status |
|---|---|---|
| Reserve (DeFi) | not a MEXC action at all | ✅ Off-exchange; outside MEXC's purview entirely |
| Trading idle → Flexible Savings | MEXC's own product, invited use | ✅ ToS-safe by construction |
| MX-Kickstarter | single account, ≤100k MX, never split | ✅ (agent 24 §4 Strategy C — FAQ §4 multi-account tripwire respected) |
| Airdrop farming | single wallet, genuine activity | ⚠️ no sybiling; one identity (`16` §5.1); book as speculation |

**No new order-rate, cancel-ratio, or multi-account exposure is introduced.** The YieldSleeve is fleet-level config + an off-exchange transfer, not a trading-strategy change.

### 6.4 Implementation touch points (file:line)

| Change | Where | What |
|---|---|---|
| Set the **honest cash benchmark** | `rapana/cli.py:1061,1077` (`--cash-return`) + `rapana/backtest/carry.py:115` (`cash_return`) + `funding_spike.py` | Default `cash_return` to **0.035** (3.5% stablecoin yield), not 0.0. Every validator now fails strategies that don't clear the real-yield floor. |
| Sleeve-aware capital split | `rapana/fleet/capital.py:11-48` (`StagedCapital`) | Add a sibling `ReserveSleeve` dataclass: `reserve_fraction` (default 0.7) routed to a yield account; `StagedCapital.available()` (`capital.py:34`) continues to govern only the *trading* sleeve. The fleet's `equity` denominator (used at `portfolio.py:55-59`) should be **trading-sleeve equity**, not total. |
| Track reserve yield accrual | `rapana/fleet/portfolio.py:9-59` (`PaperPortfolio`) | Add a `reserve_accrued: Decimal` field updated each cycle by `reserve_balance × daily_rate`. Do **not** let it inflate the trading sleeve's apparent equity (would fake out the autopilot demote/halt in `autopilot.py`). |
| Wire the existing yield analyst | `rapana/agents/yield_strategist.py:13-31` (currently neutral-by-default) | Inject a `yield_fn` that compares MEXC Flexible vs DeFi sUSDS and emits a low-conviction `"yield"` `Signal` (`signals.py:20`) so the orchestrator (`orchestrator.py:73,86`) sees it. Keep it **uncorrelated carry**, strength ≤ 0.2, so it never overrides directional alpha. |
| Sweep scheduler (cron, not per-cycle) | new `rapana/fleet/yield_sleeve.py` | Daily job: (1) reconcile reserve sleeve balance vs target `reserve_fraction`; (2) rebalance trading idle buffer into/out of MEXC Flexible; (3) log accrued yield to the journal (`rapana/journal/`). Human-approved transfers only (reserve movements are slow). |
| MX-Kickstarter carry | already specified in `24-airdrops.md` §5.2 (fleet scheduler `rapana/fleet/kickstarter.py`) | reuse as-is — it is the carry-sleeve implementation |

### 6.5 What the YieldSleeve deliberately does NOT do
- **No volatile-pair AMM LP** (IL risk, §3).
- **No algorithmic stablecoins** (UST/USDD — agent 21 §2.2; zero-recovery tail).
- **No leveraged looping** ("USDC → borrow → re-supply" degen strategies; liquidation + funding risk, not capital preservation).
- **No concentrated liquidity** (Uniswap v3 tight ranges; §3 amplification).
- **No multi-account anything** (`16` §5.1; MEXC Kickstarter FAQ §4).
- **No booking airdrop farming as yield** (§4 — it is a lottery).

---

## 7. Risk register (honest)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Depeg of a held stable** (USDC/DAI/USDS) — collateral contagion event | Low, but **fat-tailed** (SVB-2023 was ~−13% intraday) | High | Diversify across ≥2 stables (USDC + USDS); monitor `21-stablecoin-depeg.md` triggers; **never** hold algorithmic stables |
| **Smart-contract exploit** (Aave/Spark/Curve) | Low (Aave: never large-scale) but nonzero | High | Prefer the most-audited, longest-tenured pools; cap exposure per protocol; favor single-asset lending (R5) over LP (R6) to dodge Curve-hack-type events |
| **MEXC counterparty failure / hot-wallet hack** | Low but **career-ending if uninsured** | Very high | **This is the entire point of the Reserve sleeve** — keep the bulk in self-custody; MEXC holds only the liquid trading buffer |
| **Ethena sUSDe funding inversion** (yield collapses / negative in bear) | Medium in risk-off regimes | Medium | Treat sUSDe as a *cyclical* sleeve, not core reserve; cap at ≤10% of reserve; rotate to sUSDS when funding flips |
| **Maple/Centrifuge underwriting default** (R4 credit risk) | Medium (Maple had 2023 defaults) | Medium | Avoid for the reserve; the extra ~150bps over Aave is not worth the default risk for a *preservation* mandate |
| **MX price drawdown** (Kickstarter carry) | Medium | Medium | MX is a separately-justified position; Kickstarter is carry *on existing* MX, never a reason to acquire MX (agent 24 §3.2) |
| **Yield numbers drift** (the 3–6% floor is regime-dependent) | Certain | Low–Med | Re-query `yields.llama.fi/pools` weekly; the `cash_return` benchmark (`cli.py:1061`) should track a rolling real-yield index, not a fixed constant |
| **Fake-yield temptation** (chasing the 15–50% pools) | High (behavioral) | High | §2.2 rule: >6% on stables = emission/credit/funding/promo; verify `apyBase` vs `apyReward` on DefiLlama before sizing |
| **Airdrop farming booked as yield** | High (organisational) | Med | Separate mental account (§4.2); book expected value at $0; only realized claims (sold at open) count |

---

## 8. Sources (consolidated; DeFi rows fetched 2026-06-23)

- S1 — DefiLlama Yields API, `GET https://yields.llama.fi/pools` (15,976 pools; all DeFi APYs in §2 verified against this snapshot). UI: https://defillama.com/yields · stablecoin preset: https://defillama.com/yields/stablecoins
- S2 — DefiLlama Stablecoin Yields, https://defillama.com/yields/stablecoins (curated stable pool ranking)
- S3 — MEXC, "MEXC Earn" landing page (Flexible/Fixed Savings, On-Chain Earn, Auto-Earn; "up to 600% APR" new-user promo; FAQ on interest sources / redemption). https://www.mexc.com/earn  (learn/savings endpoints bot-gated `HTTP 403`; promo structure verified on the live page)
- S4 — MEXC, "Kickstarter Event FAQ" (mechanics, commit caps, multi-account risk-control warning). https://www.mexc.co/learn/article/kickstarter-event-faq/1
- S5 — CoinGecko Research, "What Is Airdrop Farming and How to Do It to Earn Free Crypto" (farming mechanics: fees/tx-count/duration/LP/NFT; sybil-filter + clawback reality; wealth skew). https://www.coingecko.com/research/publications/airdrop-farming
- S6 — Impermanent-loss formula: constant-product AMM closed form `IL = 2√r/(1+r) − 1`, independently recomputed (§3 table). Reference explainer: Gemini Cryptopedia, "Impermanent Loss," https://www.gemini.com/cryptopedia/crypto-impermanent-loss ; Uniswap Labs risk disclosure, https://uniswap.org/risks
- S7 — Ethena (sUSDe, funding-rate-backed delta-neutral yield), https://app.ethena.fi/
- S8 — Maple Finance (institutional underwriting pools, USDC 5.11% / USDT 4.03%), https://www.maple.finance/
- S9 — Spark / Sky (sUSDS Savings Rate ~3.6%), https://spark.fi/ · https://sky.money/
- S10 — Pendle (fixed-yield PT markets, sUSDe/sUSDe-PT), https://app.pendle.finance/
- S11 — Curve (3pool stable LP, base yield ~0% in current regime), https://curve.fi/
- Cross-ref: `07-profit-benchmark.md` (the honest profit bar / benchmark this agent sets the floor for); `21-stablecoin-depeg.md` §2 (the depeg tail that conditions every stable-yield row); `24-airdrops.md` §3 (MX-Kickstarter carry = the Carry sleeve) and §2.3 (70%-of-airdrops-never-profit, the airdrop-farming ROI anchor); `13-mexc-fees-promos.md` §4/§5.2 (Kickstarter economics); `16-mexc-tos-envelope.md` §5 (Safe Operating Envelope, esp. one-identity / no-multi-account).

---

## Summary (≤4 lines)

The most consistent crypto "profit" is **not trading alpha — it is ~3–6% structural real yield on dollars** (live DefiLlama 2026-06-23: sUSDS 3.6%, BlackRock BUIDL 3.5%, Ethena sUSDe 3.5%, Maple/Centrifuge 5–6% *with credit risk*, blue-chip Aave/Spark stable-lending median **~2.6%**, stable+stable LP base **~0–2%**; **>6% on stables is always emission/credit/funding/promo**). **Airdrop farming is not yield — it's a lottery** (~70% of airdrops never profit holders; high variance, poor capital efficiency, sybil/clawback risk), so book it at $0 expected. The **YieldSleeve** splits equity into a **self-custody Reserve (~70%, Aave/Spark sUSDS ~3.6%, removes MEXC counterparty risk)** + a **liquid MEXC Trading sleeve (~20–40%, idle buffer in Flexible Savings ~1–3%)** + a small **Kickstarter/airdrop carry sleeve** — blended floor **~2.5–3.5%/yr**. Wire this as the **`cash_return = 0.035` benchmark at `cli.py:1061`** so any "profitable" strategy that doesn't clear ~3.5% net is correctly flagged as **fake profit**.
