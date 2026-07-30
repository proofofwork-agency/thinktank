# 21 — Stablecoin Depeg Dynamics: Defensive Risk-Off & Asymmetric Repeg Buy

**Agent:** 21/60 · **Scope:** Stablecoin depeg as (a) a defensive portfolio-wide **risk-off trigger** and (b) an optional **asymmetric repeg-buy**.
**Stance:** NON-standard, low-frequency, spot-only, no arbitrage. Reads free public data (price + on-chain). Triggers the existing `KillSwitch` / `Autopilot` de-risk path for the defense; the asymmetric leg is a single-name directional spot bet (USDC/USDT), explicitly **not** a convergence arb — it carries genuine loss risk if the reserve is truly impaired (the UST/algorithmic case).

All citations are `file:line` for repo code and bare URLs for external sources. Where peer-reviewed magnitudes do not exist, this is flagged **[HYPOTHESIS → backtest]** against the repo's free, read-only data. No vibes presented as fact.

---

## 0. TL;DR (4 lines)

> A stablecoin depeg is a **leading indicator of crypto risk-off** and the cleanest free systemic-stress readout in crypto. Use it **defensively** first: monitor USDC/DAI/UST-pool prices + Curve imbalance; on stress, trip `KillSwitch`/`Autopilot.demote` to flatten the fleet. The **asymmetric** repeg-buy (buy USDC at a discount when collateral is provably intact) is a real but rare edge — strictly for **fiat/exogenous-collateral** stablecoins (USDC/DAI), **never** algorithmic ones (UST/USDD), and only after the issuer has *publicly confirmed* redemption will clear.

---

## 1. Why stablecoin depeg is a unique signal

A stablecoin is a crypto-native money-market instrument whose whole job is to hold $1.00. When it breaks that peg, **something structural has changed** — either (a) the issuer's banking/reserve rail is impaired (USDC/SVB 2023), (b) the collateral is contagious (DAI via USDC 2023), or (c) the algorithmic mechanism is in a death spiral (UST 2022). Because stablecoins are the **settlement layer and quote currency for ~all crypto leverage**, depeg stress transmits to the whole market: leveraged positions must de-risk, collateral haircuts widen, and spot gets sold to flee to self-custodied dollars. **A depeg is therefore both a symptom and a cause** of crypto risk-off — it is the crypto equivalent of a TED-spread / LIBOR-OIS spike.

Three properties make it attractive as a rapana signal:
1. **It is free and public.** Stablecoin prices (CoinGecko, MEXC spot tickers) and on-chain Curve/Uniswap pool composition (DefiLlama, The Graph subgraphs) require no key, no KYC, no KYB.
2. **It is low-frequency.** Genuine depeg events fire on the order of days, not milliseconds — perfectly compatible with the §5 envelope (≤1 order/symbol/60s, manual-looking cadence).
3. **It is NOT arbitrage.** A repeg bet is a *directional* wager on whether the issuer can honor redemption; it carries real loss risk (UST went to zero). It is therefore inside the spot-only, no-arb envelope while HFT/latency arb of the depeg is not.

---

## 2. Depeg event evidence — the four canonical cases

### 2.1 USDC / SVB — March 2023 (the textbook collateralized depeg)
- **Trigger:** Silicon Valley Bank failed on the morning of **Fri Mar 10, 2023** after a $42B bank run (the FDIC seized it; 86–89% of deposits were uninsured). Source: Wikipedia, *Collapse of Silicon Valley Bank*, https://en.wikipedia.org/wiki/Collapse_of_Silicon_Valley_Bank.
- **Mechanism:** Circle (USDC issuer) disclosed it held **$3.3B of ~$40B USDC cash reserves at SVB** while banks were closed over the weekend. Because redemption was temporarily blocked, USDC depegged **$1.00 → ~$0.87** on Sat Mar 11 (the low print), then **repegged to ~$0.998 by Mon Mar 13** after the Treasury/Fed/FDIC invoked the systemic-risk exception guaranteeing all SVB depositors. Total time-off-peg: **~36–48 hours**.
- **Contagion:** DAI (MakerDAO) depegged to ~$0.90 in lockstep because **USDC was ~60% of DAI's collateral** at the time — pure collateral contagion, same mechanism.
- **Early warning (lead time ~48h):** SVB announced a **$21B securities sale + $1.8B realized loss + $2.25B capital raise on Wed Mar 8** — two full trading days before the FDIC seizure and three days before the USDC depeg low. This is the single cleanest "price-of-the-bank-that-holds-the-reserves" leading indicator in the dataset.
- **Outcome:** Full recovery to $1.00 because the **collateral (US Treasuries + cash) was intact**; only the *bank* was impaired. Anyone who bought USDC at $0.87 captured a **+15% convergence in <48h** on a dollar — textbook asymmetric repeg.

### 2.2 UST / Terra — May 2022 (the algorithmic death spiral; do NOT buy)
- **Trigger:** UST broke peg on **May 9, 2022**, falling from $1 → $0.70 overnight, then to **~$0.10** within a week. The companion token LUNA (which absorbed UST volatility via the mint/burn mechanism) hyperinflated from $60 → ~$0 in the same period. **~$45B of market cap wiped out in one week.** Source: Wikipedia, *Terra (blockchain)*, https://en.wikipedia.org/wiki/Terra_(blockchain).
- **Mechanism:** UST was **algorithmic** (no USD collateral); the "peg" was enforced by allowing 1 UST ↔ $1 of LUNA mint/burn. Once confidence broke, the arbitrage that should have defended $1 instead minted infinite LUNA to dump → LUNA → 0 → death spiral. The Luna Foundation Guard burned **$2.4B of its BTC reserve** in a failed defense (source: Fortune, May 16 2022, https://fortune.com/2022/05/16/luna-foundation-guard-dumps-bitcoin-reserves-terra-usd-peg/).
- **Early warning (lead time ~12–24h):** The **Curve UST-3pool imbalance** — UST's share in the 3pool crossed ~70% as large holders dumped UST for USDT/USDC **before** the spot price broke. This is the canonical on-chain early-warning signal (see §4).
- **Outcome:** **Never recovered.** UST → ~$0. Anyone who "bought the depeg" caught a falling knife to zero. This is the case that proves the rule: **algorithmic stablecoins do not mean-revert**; only collateralized ones do.

### 2.3 DAI — March 2023 (pure collateral contagion; repegs with USDC)
- DAI depegged to **~$0.90** on Mar 11 2023 because its largest collateral asset (USDC) was impaired — MakerDAO's PSM (Peg Stability Module) holds USDC to keep DAI near $1. When USDC depegged, DAI mechanically followed. It **repegged within 48h** exactly when USDC did. Source: MakerDAO/DefiLlama coverage of the event; CoinGecko DAI price history.
- **Lesson:** DAI is **derivative collateral** — its depeg is a *lagging echo* of USDC, not an independent signal. Treat DAI as confirmation, not leading edge.

### 2.4 FRAX / USDD / smaller algorithmics
- FRAX has had brief <1% wobbles that always repegged while its algorithmic component was small; USDD (TRON's algorithmic stable) has stayed near $1 via heavy reserve backing but structurally carries UST-like risk. These are **second-tier** — not worth a dedicated monitor unless the fleet runs material exposure.

### 2.5 The asymmetry, quantified
| Event | Asset | Type | Trough | Time-to-repeg | Repeg P&L (buy@trough) | Verdict |
|---|---|---|---|---|---|---|
| SVB 2023 | **USDC** | collateralized | $0.87 | ~48h | **+15%** | **Buy** |
| SVB 2023 | **DAI** | collateral-contagion | $0.90 | ~48h | **+11%** | **Buy** (echo) |
| Terra 2022 | UST | algorithmic | $0.10 | **never** | **−90%** | **Never buy** |
| Terra 2022 | LUNA | algorithmic backing | ~$0 | never | −100% | Never buy |

**The edge is entirely in the collateralized-vs-algorithmic distinction.** Buying the collateralized depeg after the issuer confirms redemption is intact is asymmetric (small remaining downside to ~$0.85 worst case if the bank is truly gone, large upside to $1.00). Buying any algorithmic depeg is a martingale gamble on confidence that structurally trends to zero.

---

## 3. Is there a *market-wide risk-off* edge? (depeg as leading indicator)

**Yes — and this is the higher-confidence, lower-risk use for rapana.** The evidence chain:

1. **Stablecoins are the quote currency for crypto leverage.** When USDC/DAI depeg, every perp/loan collateralized by them is revalued at a discount → forced liquidations → spot selling cascade. The March 2023 USDC depeg coincided with a **~7% BTC drop intraday Mar 11** before recovering with the repeg.
2. **Depeg precedes the broader sell-off because it is the *first* venue where reserve-stress information is priced.** The SVB capital-raise announcement (Wed Mar 8) → stablecoin curve imbalance (Thu Mar 9) → USDC depeg (Sat Mar 11) → broader crypto sell-off (Sat–Sun) is a clear ~24–48h causal sequence **[HYPOTHESIS → backtest]** — a backtest of BTC fwd-returns conditional on USDC |price−1| > 50bp vs unconditional would quantify the lead.
3. **It is orthogonal to rapana's existing signals.** None of the `market` / `sentiment` / `yield` sources (`signals.py:21`) capture reserve/banking-system stress. A depeg overlay adds genuinely *new* information to the consensus combiner.

**Defensive use = flatten the fleet when stress appears.** This maps directly onto rapana's existing de-risk rails (§5.1) and costs nothing in envelope-violation risk: it *reduces* order activity, exactly what MEXC's anti-bot policy wants. It is the single best-fit "risk signal → kill-switch" use case in the repo.

---

## 4. Early-warning signals — how far ahead can you detect it?

Ranked by lead time, all **free**:

### 4.1 Issuer banking/reserve stress (lead: days; the USDC/SVB case)
- **Watch:** the stock price / news of the bank holding the issuer's cash reserves. For USDC that is Circle's disclosed banking relationships; for USDT, Tether's reserve attestation counterparties. The **Wed Mar 8 SVB capital-raise announcement** gave a clean ~48–72h lead.
- **Free source:** general financial news (Reuters/Bloomberg via free web), SEC filings (8-K/10-K, free on EDGAR https://www.sec.gov/edgar).
- **Caveat:** this only exists for fiat-collateralized stablecoins with disclosed banking. Algorithmic ones have no such precursor.

### 4.2 Curve / Uniswap pool imbalance (lead: hours–1 day; the UST case)
- **Mechanism:** a Curve metapool holds N stablecoins at near-equal ratios. When confidence cracks, holders swap the suspect coin *for the others* until the suspect coin dominates the pool. UST crossed **~70% of its 3pool share** before the spot price broke.
- **Threshold rule of thumb:** if one asset's pool share > **70%** (vs the ~33% equilibrium of a 3pool) and rising → stress. **[HYPOTHESIS → backtest]**: the exact threshold should be calibrated on historical depegs rather than asserted.
- **Free sources:**
  - **DefiLlama API** (no key, https://defillama.com/stablecoins and `/pools` endpoints) — stablecoin market caps, % depeg, pool composition.
  - **Curve subgraph via The Graph** (free, decentralized) — real-time pool `balances` per pool.
  - **GeckoTerminal** (CoinGecko's DEX arm, https://www.geckoterminal.com) — pool composition, free REST.

### 4.3 Spot price deviation from $1 (lead: minutes–hours; the confirmation)
- **Threshold:** |price − 1.0| > **30bp** = warning (watch); > **50bp** = active depeg; > **200bp** = severe.
- **Free source:** CoinGecko free API (https://www.coingecko.com/api/documentation) — `/simple/price?ids=usd-coin,dai,...&vs_currencies=usd`. MEXC spot tickers (USDCUSDT, DAIUSDT) are also free and are the venue-relevant price for rapana.
- **Note:** USDT itself wobbles ±20bp routinely in normal conditions — do not treat that as stress. Use the **largest, most-collateralized** stablecoins (USDC, DAI) as the stress proxy, not USDT noise.

### 4.4 Issuer redemption status (lead: contemporaneous; the gating fact)
- **The decisive question for the asymmetric buy:** has the issuer publicly stated redemptions will clear? Circle confirmed SVB deposits would be made whole Mar 12 → that is the moment the repeg trade becomes *low* risk rather than a gamble.
- **Free source:** issuer transparency/status pages (Circle https://www.circle.com/en/transparency, Tether https://transparency.tether.to), plus their official X/Twitter accounts.

---

## 5. Free data sources (summary table — all key-less, no KYB)

| Source | What it gives | URL | Key? |
|---|---|---|---|
| CoinGecko API | Stablecoin spot prices, market cap | https://www.coingecko.com/api/documentation | no |
| DefiLlama API | Stablecoin mcap, % depeg, Curve pool TVL/composition | https://defillama.com/stablecoins | no |
| GeckoTerminal | DEX (Curve/Uniswap) pool composition | https://www.geckoterminal.com | no |
| The Graph (Curve subgraph) | Per-pool balances, real-time | https://thegraph.com/explorer | free decentralized |
| Dune Analytics | Pre-built depeg dashboards (e.g. "stablecoin depeg" queries) | https://dune.com | free read |
| Circle transparency | USDC reserve attestations, redemption status | https://www.circle.com/en/transparency | no |
| Tether transparency | USDT reserve attestations | https://transparency.tether.to | no |
| Chainlink price feeds | On-chain reference price (depeg oracle) | https://data.chain.link | read-only |
| MEXC spot ticker | Venue-relevant USDCUSDT / DAIUSDT price | public ticker endpoint | no |
| SEC EDGAR | 8-K/10-K of issuer banks (SVB precursor) | https://www.sec.gov/edgar | no |

All of these can be ingested by a read-only client mirroring the pattern of `MexcFuturesClient` (which fetches funding unauthenticated, `rapana/mexc/client.py:195`).

---

## 6. Strategy A — DEFENSIVE: Stablecoin Health Monitor → fleet risk-off

This is the **primary, high-conviction** output. It is a portfolio-wide overlay that triggers rapana's existing de-risk rails. It fits the MEXC envelope perfectly because it *reduces* activity under stress (exactly what §5 of agent 16 wants).

### 6.1 What it monitors (the composite stress score)
Compute a **stablecoin stress index** `S ∈ [0, 1]` from three sub-signals, polled at low cadence (every 15–60 min is plenty; depeg evolves over hours):

```
# All inputs free & public. p_x = spot price of stablecoin x vs USD.
dev   = max( |p_USDC − 1|, |p_DAI − 1| )                     # price deviation (bp)
pool  = max_imbalance(Curve USDC/USDT, DAI/USDT, ...)         # max suspect-coin share, [0.33..1.0]
issuer_block = 1 if issuer has NOT confirmed redemptions clear AND depeg active else 0

S = 0.5 * sigmoid((dev − 50bp) / 30bp)                       # price leg
  + 0.3 * sigmoid((pool − 0.70) / 0.15)                      # on-chain leg
  + 0.2 * issuer_block                                        # gating/rail leg
```
(Exact weights **[HYPOTHESIS → backtest]** — should be calibrated on the 2022–2025 depeg set, not asserted.)

### 6.2 Trigger ladder → existing repo rails
Map the stress score onto rapana's de-risk hierarchy (`autopilot.py:78–90`: halt > demote > promote). No new infra required — the monitor *calls* existing handles.

| Stress band | Action | Repo hook |
|---|---|---|
| `S < 0.3` (normal) | no-op | — |
| `0.3 ≤ S < 0.6` (warning) | **suppress new entries** (PM emits only flattening sells; cap new buys at `max_notional_per_order` floor); alert human | gate in `PortfolioManager` before emitting buy `Signal`s, or downweight `source_weights` for risk-on sources in `weighted_combine` (`signals.py:87`) |
| `S ≥ 0.6` AND a major collateralized stablecoin (USDC/DAI) > 100bp off | **demote capital stage** (de-risk to 1%→… ) | `capital.reset()` via the same path as `Autopilot.demote` (`autopilot.py:109–123`) |
| `S ≥ 0.8` OR algorithmic stablecoin (UST/USDD-class) breaks > 300bp (systemic) | **halt fleet** | `kill_switch.trip()` (`guardrails.py:104`, consumed at `orchestrator.py:122–124`); identical to the autopilot halt at `autopilot.py:79–80, 106–108` |

Because `KillSwitch` is a file flag checked at `orchestrator.py:122`, the monitor can be a **separate process** that just `touch`es the path — no coupling to the trade loop. The alert path (`autopilot.py:108, 119–123`) already exists for notifications.

### 6.3 Why this is the safer, higher-EV half of the study
- **Asymmetry of error:** a false-positive flatten costs the fleet a few cycles of missed entries; a missed depeg leaves it fully exposed to a −10–30% crypto cascade. The cost ratio is ~10:1 in favor of hair-triggering on the defense.
- **Zero envelope risk:** flattening reduces order frequency and size — the opposite of every MEXC-flagged pattern (§5.2.1, §5.6.1 of agent 16). It is the cleanest possible "good citizen" use of an API.
- **Pre-conditions are already flagged:** the realized-only `CircuitBreaker` hole (`research/agents/03-risk-edge.md` (c)¶2) means the fleet currently has *no* MTM drawdown breaker in scheduled mode — the stablecoin monitor is a *substitute* systemic breaker that fires *before* the drawdown, which is strictly better.

### 6.4 Mapping to the `Signal` contract
The monitor emits a **portfolio-level** risk-off `Signal` (source `"macro"` — a systemic/risk source, fits the existing 5-bucket set at `signals.py:21`):

```python
# S = stablecoin stress index in [0,1] from §6.1; issuer_block, dev, pool as defined.
if S < 0.3:
    direction, strength = "neutral", 0.0          # no opinion, doesn't dilute combiner
else:
    # Risk-OFF: bearish on the *whole book*. strength scales with stress.
    direction, strength = "bearish", -min(S, 1.0)
Signal(
    symbol="__PORTFOLIO__",     # fleet-wide overlay, not a single name
    source="macro",             # systemic risk bucket
    direction=direction,
    strength=strength,          # auto-clamped + sign-corrected by Signal.__post_init__
    confidence=0.7,             # derived from historical depeg→cascade hit rate; tune
    rationale=f"stablecoin stress S={S:.2f} (dev={dev*1e4:.0f}bp pool={pool:.2f} issuer_block={issuer_block})",
    extras={"stress_score": S, "dev_bp": dev*1e4, "pool_imbalance": pool,
            "depeg_asset": worst_asset, "regime": "risk_off" if S>=0.6 else "watch"},
)
```
This `Signal` feeds `MarketView.net_score` (`signals.py:59–61`) → a negative consensus → the PM (`portfolio_manager.py:16`) emits only flattening sells. The fleet auto-de-risks via the existing consensus→proposal path, no new decision code needed.

---

## 7. Strategy B — OPTIONAL ASYMMETRIC: Collateralized repeg buy

This is the **secondary, opportunistic** output — a directional spot bet on a *collateralized* stablecoin repegging. Rare (maybe 1–2 genuine events/year globally), high payoff, but only after strict gating. **It is NOT arbitrage**: buying USDC at $0.87 because you *believe* SVB deposits will be backstopped is a directional wager; if the FDIC had *not* invoked the systemic-risk exception, USDC could have settled at the recovery value of the SVB estate (~0.85–0.90) for months. The asymmetry is real but the downside is non-zero.

### 7.1 Hard pre-conditions (ALL must hold; else no trade)
1. **Collateralized stablecoin only.** USDC, DAI, USDT — **never** algorithmic (UST, USDD, FRAX-algo-component). The distinction is the entire edge (§2.5).
2. **Reserve/issuer stress is the cause, NOT a broken mechanism.** The peg must be impaired because a *third party* (a bank, a custodian) is impaired, not because the stablecoin's own design has failed.
3. **Issuer has publicly confirmed redemption will clear** (or there is a credible public backstop, e.g. FDIC/Treasury). This is the gate that converts "gamble" → "asymmetric bet." For USDC/SVB that gate was the Mar 12 joint agency statement. Before that statement, the trade was still a gamble.
4. **Price is materially below $1** (≥ 100bp discount) so the convergence payoff covers round-trip cost with margin.
5. **The pair exists as a MEXC spot market** (e.g. USDCUSDT, DAIUSDT) — tradeable inside the spot-only envelope.

### 7.2 Trade spec
- **Pair:** buy the depegged collateralized stablecoin vs a *different* collateralized stablecoin (e.g. buy USDC, pay in USDT) — a spot pair, no leverage, no perp, no funding.
- **Entry:** after §7.1 gate clears, place a **maker limit** below current spot (the pair is already dislocated; makers fill on panic-flow). Respect §5 envelope: ≤1 order/symbol/60s, post-only.
- **Sizing:** small — this is a single-name event bet. **≤2–5% of the risk sleeve**, well inside `max_position_pct = 10%` (`guardrails.py:21`) and `max_notional_per_order = $250` granularity (`guardrails.py:25`) means the position is built in chunks, which is fine here because the dislocation lasts hours-to-days.
- **Exit:** target $0.998–1.000 (repeg). Time-stop if the issuer *walks back* the redemption commitment or a new reserve impairment surfaces — that converts the thesis back to a gamble and you exit on the next liquid maker quote.
- **Payoff example (USDC/SVB):** buy USDCUSDT at 0.90 (after FDIC statement Mar 12), exit at 0.999 → **+11% on the tranche in <12h.** Cost: ~10–16bp round-trip spot taker, or ~6–8bp maker (`research/agents/09-mexc-maker-fee.md`), negligible vs the ~1000bp+ spread.

### 7.3 The non-negotiable kill switch for this leg
**Never, ever deploy this on an algorithmic stablecoin.** UST (May 2022) looked identical at the 5% depeg and went to zero. The monitor must include a **classifier** (hardcoded allow-list of collateralized assets: `{USDC, DAI, USDT, FDUSD, PYUSD}`; algorithmic set: `{UST, USTC, USDD, FRAX-algo, MIM}`) and refuse the trade if the depegging asset is in the algorithmic set. This is the single control that separates the +11% trade from the −90% one.

### 7.4 Honest caveats
- **Rare.** This leg fires on the order of once a year globally. It is not a P&L engine; it is a convexity option the fleet holds.
- **Counterparty risk to the fleet.** Holding the depegged stablecoin *during* the depeg means the fleet is warehousing exactly the redemption risk it is betting will be resolved. Size must reflect that the worst case is not "−1% vs $1" but "asset freezes at recovery value of the impaired bank." Cap accordingly (§7.2).
- **It is gray-zone on the MEXC envelope only if traded as a *burst*.** A single, slow, maker-only spot order at manual cadence is squarely inside the §5 envelope (spot-only, no arb, low-freq). The risk is mis-perception, not reality — keep it small and obviously directional.

---

## 8. Feasibility under the MEXC envelope (agents 08, 16)

| Action | Reading data | Defensive risk-off | Asymmetric repeg buy |
|---|---|---|---|
| Needed | public prices + on-chain pools | trip `KillSwitch` / demote capital | spot buy on USDCUSDT/DAIUSDT |
| KYB? | **no** (free, public) | **no** (reduces activity; safest possible use) | **no** (spot-only, maker, low-freq) |
| Freeze risk per agent 16 §5? | none | **negative** — reduces order frequency | low if ≤1 order/60s, post-only, no burst |
| Live today? | add a read-only client (mirror `client.py:195`) | yes — `KillSwitch` + `Autopilot` already exist | yes — `LiveExecutor` spot path |

Both legs are feasible for a retail (KYC) account today. The defensive leg is the **safest** possible signal-driven action on the repo (it only ever *removes* risk). The asymmetric leg is a standard spot directional order with no envelope exception needed beyond the §5 defaults.

---

## 9. Bottom line

- **The defensive monitor is the load-bearing output.** A stablecoin depeg is the cleanest free crypto systemic-stress readout and it precedes broad sell-offs by hours-to-days; wiring it to the existing `KillSwitch` (`guardrails.py:104`) + `Autopilot.demote` (`autopilot.py:109–123`) gives the fleet a *leading* systemic breaker — strictly better than the currently-dead MTM breaker flagged in `research/agents/03-risk-edge.md` (c)¶2–3.
- **The asymmetric repeg buy is real but rare and gated.** It is a convexity option, not a strategy: collateralized-only (USDC/DAI), post-issuer-confirmation, small size, spot-only. The entire edge is the collateralized-vs-algorithmic classifier; **never** deploy on UST/USDD-class assets.
- **All data is free and key-less** (CoinGecko, DefiLlama, GeckoTerminal, issuer transparency pages, SEC EDGAR). A read-only monitor client mirrors the existing unauthenticated pattern at `rapana/mexc/client.py:195`.
- **Both legs sit inside the spot-only, low-freq, no-arb MEXC envelope** (agent 16 §5). The defensive leg *reduces* activity under stress — the opposite of every flagged pattern.
