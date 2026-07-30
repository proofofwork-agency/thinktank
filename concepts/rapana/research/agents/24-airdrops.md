# 24 — Airdrop snapshot / claim-date price dynamics & the Kickstarter yield sleeve

**Agent:** 24/60 · **Scope:** Post-airdrop price-impact evidence (JUP/ARB/STRK/ENS/OP/TIA/UNI/JTO/Blur), the claim-window pattern, post-washout accumulation, and the MEXC MX-Kickstarter yield sleeve.
**Stance:** NON-standard, low-frequency, event-driven. Spot-only on MEXC; no arb. Honors the Safe Operating Envelope in `16-mexc-tos-envelope.md` §5. Cross-references the Kickstarter mechanics in `13-mexc-fees-promos.md` §4/§5.2 and the listing-event patterns in `10-mexc-listings.md`.

**Status of evidence:** Core price-impact magnitudes are **industry-analyst figures** (Chainalysis, IntoTheBlock, chainscorelabs, onchaineconomics) cross-checked against observable price history. Not peer-reviewed. **[HYPOTHESIS → backtest]** the MEXC-specific realized distribution on the free historical download (`mexc.co/zh-CN/market-data-download`) before sizing up — same discipline as agent 10 §6.

---

## 0. TL;DR (4 lines)

> Airdrop recipients have **zero cost basis and immediate liquidity**, so the post-claim dump is the most consistent event effect in crypto: **~50–85% of tokens are sold within 7 days** and median drawdown is **−20 to −40% in weeks 1–4** (ARB −87%, STRK −62%, OP −58% over 30d; STRK fell ~60% in 2 days). The clean ToS-safe edges are **(A) VETO longs / defer entries into claim windows**, **(B) accumulate after the washout exhausts (month 1–3) on utility-gated names**, and **(C) MX-Kickstarter as an uncorrelated yield sleeve** (~10–20% annualized on committed MX, paid in high-beta tokens that *themselves* dump — so sell-at-listing discipline is mandatory). Strategy C is MEXC's own flagship retail product and is ToS-safe by construction; A and B are directional spot, single-account, clearly inside the envelope.

---

## 1. The mechanism — why the post-claim dump is structural, not anecdotal

The dump is not sentiment; it is **mechanics**. Two structural facts combine:

1. **Zero cost basis.** Airdrop recipients acquired tokens for free, so *every positive price is profit*. Basic dominance argument: sell at any positive price. ([onchaineconomics](https://www.onchaineconomics.io/guides/airdrop-economics): "selling occurs at any positive price since all proceeds represent profit.")
2. **Supply inflation at TGE.** The airdrop *is* a circulating-supply shock — 5–17% of supply minted to mercenary wallets overnight. ([chainscorelabs](https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure): "Token supply inflates 5–20% overnight.")

The buyer of last resort is absent: recipients *are* the new supply, and there is no matching new demand at the claim instant. The result is a **predictable, scheduled supply overhang** that resolves downward until selling exhausts — the crypto analog of an IPO unlock, except the tokens were free.

**The irony that makes Strategy C work (and dangerous):** the very same dump dynamic means the *airdrop tokens you receive* from MEXC Kickstarter will also dump. The yield is only realized if you sell at listing open — hold the received tokens and your "yield" evaporates into the post-claim drift. This is the central operational rule of the yield sleeve.

---

## 2. Evidence — how consistent and how large? (the load-bearing numbers)

### 2.1 Comparative autopsy (analyst-compiled, chainscorelabs "Airdrop Autopsy" table)

| Token | Circ. supply inflation at TGE | Price drop (airdrop-day high → 30d) | % of airdrop sold in week 1 | Airdrop:FDV at launch | Counter-pressure driver |
|---|---|---|---|---|---|
| **Arbitrum (ARB)** | 12.75% | **−87%** | **>85%** | 1:7.8 | Uncapped claimable supply to sybils |
| **Optimism (OP)** | 5.4% | **−58%** | ~50% | 1:18.5 | Sustained linear unlocks post-TGE |
| **Starknet (STRK)** | 13.1% | **−62%** | ~70% | 1:7.6 | Concentrated CEX listings + mercenary capital |
| **Celestia (TIA)** | 16.7% | **+185%** | <20% | 1:6 | **Low float + sustained utility demand (counterexample)** |

Source: [chainscorelabs — "Airdrop Dilution: The Hidden Cost of Unearned Tokens"](https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure). TIA is the **load-bearing counterexample**: utility demand can overwhelm the dump. This is exactly what Strategy B must gate on.

### 2.2 Headline case data (cross-checked)

| Token | Claim window | Verified behavior | Source |
|---|---|---|---|
| **ARB** | Mar 2023 | Opened ~$1.40 → ~$1.10 "within days" → **<$0.90 by Apr 2023**; **60% of recipients sold or transferred to CEX within 7 days**; >90% sold within 4 months; ~−90% from post-airdrop high | [onchaineconomics](https://www.onchaineconomics.io/guides/airdrop-economics) |
| **STRK** | Claim opened 2024-02-20 12:00 UTC | **~60% drop in 2 days** — from a $4 high to under $1.90 by claim-day +2 | [CCN](https://www.ccn.com/analysis/starknet-price-drops-two-days-founders-dump-what-next-strk/) |
| **UNI** | Sep 2020 | **50% of recipients sold entire allocation within first week** (Chainalysis) | [onchaineconomics](https://www.onchaineconomics.io/guides/airdrop-economics) (citing Chainalysis) |
| **ENS** | Nov 2021 | **>60% of recipients sold immediately**; user base still expanded permanently | [chainscorelabs](https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure) |
| **OP** | 5th cycle Oct 2024 | **5× increase in wallet-emptying** after the airdrop; ~half of 54,723 recipient wallets emptied shortly after | [Cryptonews/IntoTheBlock](https://cryptonews.com/exclusives/70-of-airdropped-tokens-fail-to-deliver-profits-heres-why/) |
| **Jito (JTO)** | 2024 | **>$150M distributed**; immediate sell pressure suppressed price discovery for months | [chainscorelabs](https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure) |
| **Blur** | 2023 | **>$1B distributed** to incentivize volume; TVL + volume collapsed post-airdrop as mercenary capital exited | [chainscorelabs](https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure) |
| **JUP (Jupuary)** | Snapshot 2026-01-30 | **Trading volume +200% and +12% in the days before the snapshot** (pre-snapshot farming rally); final JUPuary redesigned 700M → 200M to "ease selling pressure" | [bitzo](https://bitzo.com/2026/01/jup-trading-volume-surges-over-200-ahead-of-jupiters-january-airdrop), [CoinCentral](https://coincentral.com/jupiter-exchange-rethinks-jup-buyback-plan-slashes-airdrop-size/), [CoinMarketCap](https://coinmarketcap.com/top-stories/69b07b735e7dbd3d697126b9/) |

### 2.3 The aggregate statistic

IntoTheBlock (via Cryptonews): in a sample of **23 airdropped tokens, only 7 (~30%) showed positive returns** — i.e. **~70% of airdropped tokens fail to deliver any profit** for holders. ([Cryptonews](https://cryptonews.com/exclusives/70-of-airdropped-tokens-fail-to-deliver-profits-heres-why/))

### 2.4 Synthesis — the canonical timeline (horizons)

| Window | Typical behavior | Consistency |
|---|---|---|
| **T−7d to T (pre-snapshot)** | Rally + volume spike as farmers/sybil operators accumulate/position to maximize allocations (JUP: +12%, vol +200%) | Moderate, token-specific |
| **T0 (claim opens)** | Local high as speculators bid "anticipating demand"; then selling begins immediately | **Very consistent** |
| **T0 to +7d (week 1)** | Concentrated dump — 50–85% of allocation sold; typical **−20 to −40%** from opening | **Very consistent** (the alpha window) |
| **+7d to +30d (month 1)** | Continued selling as large-allocation recipients distribute; **−40 to −70%** first-month drawdown is typical for weak names | **Consistent** for non-utility tokens |
| **+30d to +90d (months 1–3)** | Selling exhausts; **price stabilization**; market correlation takes over | Moderate |
| **+90d onward** | Utility/dev/ecosystem fundamentals dominate; TIA/BONK/Kamino-type recoveries separate from continued bleeders | Token-specific |

> Reading: the **claim window is a one-sided, scheduled, recurring short-the-supply-shock** opportunity — except on MEXC spot we cannot easily short, so the operative edge is **VETO/avoid + post-washout accumulate**, not naked shorting (see §4).

---

## 3. The MEXC Kickstarter yield sleeve — is point-farming low-risk yield? (Strategy C)

Agent 13 (`13-mexc-fees-promos.md` §4, §5.2, Tactic C) flagged Kickstarter as "the cleanest real yield." This section adds the **quantitative ROI realism + the dump-irony caveat**.

### 3.1 Mechanics (verified verbatim from the official MEXC Kickstarter FAQ)

- **What it is:** a pre-launch event; users vote with MX, the winning project airdrops its token to all successful voters. ([Kickstarter Event FAQ](https://www.mexc.co/learn/article/kickstarter-event-faq/1))
- **Eligibility:** account must have completed **≥1 futures trade** of any size, and hold **≥5 MX for 24 consecutive hours** before the event (snapshot = *minimum* MX across 3 random snapshots in the day, UTC+8).
- **Commit range:** min 5 MX, **max 100,000 MX per account.**
- **MX is NOT frozen/spent:** "The committed MX will be used to calculate rewards and will not be frozen." You retain custody, fee-discount utility, and burn benefit — **high capital efficiency**.
- **Reward formula:** `your_reward = (your_valid_MX / all_users'_valid_MX) × total_prize_pool`, multiplied by a referral coefficient (V1 ×1.0 → V7 ×1.75).
- **The explicit multi-account tripwire (load-bearing for ToS):** FAQ §4 — *"If a single user commits a total of more than 100,000 MX across multiple accounts, the associated accounts may trigger the platform's risk control measures."* MEXC is actively watching for split-account farming.

### 3.2 Realistic ROI (illustrative — verify against the account's own `/activity-reward-records`)

Using live data points: a recent session (XEFFY) had a **30,000 USDT prize pool**; the ZYLO session (agent 13) saw **13.45M MX committed** (~$23M at MX≈$1.73).

| Parameter | Value | Basis |
|---|---|---|
| Pool size (typical) | ~$20k–$50k USDT equiv | XEFFY = 30,000 USDT |
| Total committed MX (a hot session) | ~10–15M MX (~$17–26M) | ZYLO = 13.45M |
| **Per-session yield on committed capital** | **~0.10–0.30%** | pool ÷ total committed |
| Sessions/week | ~1–3 | MEXC lists Kickstarter regularly |
| **Gross annualized yield on committed MX** | **~10–20%** | per-session × ~104/yr, before token dump |
| Capital lockup | **None** (MX not frozen) | FAQ §2 |
| What you actually keep | A stream of newly-listed tokens | high-beta, **negative post-listing drift** |

**The honest read:** ~10–20% annualized *gross* on the MX you commit, but **paid in tokens that this very research shows dump post-listing**. Two operational consequences:
1. **Sell-at-listing-open discipline is mandatory.** Holding the received tokens converts your yield into the −20–70% post-claim drift. The yield exists only if you liquidate at the listing pop (agent 13 Tactic E; consistent with `10-mexc-listings.md` §2 first-tick behavior — but you're a *recipient*, not chasing the tick, so you avoid the 30027/30028 halt trap).
2. **The real risk is MX price drawdown**, not the farming itself. You are long MX while committed. Size MX as a position with its own risk budget (agent 13 §8). The Kickstarter yield is *additive carry on an existing MX holding*, not a reason to acquire MX.

### 3.3 Is it "low-risk yield"? — verdict

**Yes, conditionally.** Capital is not locked (no opportunity cost beyond MX price exposure); the mechanism is MEXC's own flagship retail product; rewards accrue predictably. The risks are: (a) **pool crowding dilutes per-MX share** as total commitment grows, (b) **the received tokens dump**, and (c) **MX price exposure**. Risk-adjusted, it is genuine uncorrelated carry **only** with sell-at-open discipline and a separately-justified MX position. Without those two, it is a token-distribution lottery dressed as yield.

---

## 4. ToS analysis — what is safe on MEXC?

All three strategies must pass `16-mexc-tos-envelope.md` §5.1 row-by-row. Verdict per strategy:

### Strategy A — claim-window AVOID / short-bias

| Envelope row | Status |
|---|---|
| Spot-only | ✅ implemented as **inaction / reduce / defer-entry**, not as a futures short (futures auto-trading is KYB-gated, `16` §2.3) |
| Directional + genuine market risk | ✅ going flat / underweight into a claim is genuine directional exposure, not a hedge |
| No arb / no cross-venue | ✅ single-venue, single-account |
| Order rate / cancel ratio | ✅ a VETO is *fewer* orders, not more |
| Event blackout ±5 min | ✅ we are *avoiding* the event window, not concentrating in it |

**ToS-safe.** This is the cleanest version. **Do NOT implement as a perp short on the retail sleeve** — that needs KYB and trips §5.6.2 if synchronized. The retail-safe expression is: **veto new longs and trim existing longs in the ±7d claim window.** A genuine directional reduction is exactly the "manual-looking cadence" MEXC wants.

### Strategy B — post-washout accumulate

| Envelope row | Status |
|---|---|
| Spot, postOnly maker limit | ✅ accumulate via resting limit bids |
| Low-freq (entries spaced ≥60s, rounds ≥5 min apart) | ✅ scale-in over days/weeks |
| ≤2% of symbol 24h volume | ✅ small caps tighten per `16` §5.1 |
| Genuine directional long | ✅ real market risk |

**ToS-safe.** Standard directional accumulation; the only novelty is the *timing trigger* (post-claim washout + utility gate).

### Strategy C — MX-Kickstarter yield sleeve

| Envelope row | Status |
|---|---|
| MEXC's own product, invited use | ✅ "identify high-quality projects … bring airdrop benefits to MEXC users" (FAQ §1) |
| Single account, one identity | ✅ **CRITICAL:** FAQ §4 explicitly flags >100,000 MX across multiple accounts → risk control. One account only. |
| Eligibility futures trade | ⚠️ requires ≥1 futures trade. **On the retail spot-only sleeve this is a one-time manual futures tick**, not automated futures trading — acceptable, but log it as manual. |
| Sell-at-open of received tokens | ⚠️ the received-token liquidation is a *spot* sale (or Convert, `13` §2.1) — if via API it loses 0-fee; route manually/web per `13` Tactic A. |
| No multi-account farming | ✅ enforced structurally (single key, single IP per `16` §5.1) |

**ToS-safe by construction** — it is the product MEXC runs. The two operational ToS touchpoints: (1) **never split MX across accounts** (FAQ §4); (2) **route the received-token sale through non-API channels** to preserve 0-fee spot (`13` §1, §6 Tactic A). The eligibility futures trade is a one-off manual action, not automated futures.

---

## 5. Signal specs (wiring into `signals.py`)

The repo's `Signal` dataclass (`rapana/signals.py:17-46`) takes `symbol, source, direction, strength∈[-1,1], confidence∈[0,1], rationale, extras`. Existing sources: market/sentiment/macro/arbitrage/yield (`signals.py:21`). Propose **one new source `"airdrop"`** for the price-dynamics signals (A, B); Strategy C reuses **`"yield"`** as it is fleet-level carry, not a per-symbol trade.

### 5.1 New agent: `AirdropAnalyst` (`rapana/agents/airdrop.py`, mirror `agents/market.py`)

```
class AirdropAnalyst(Analyst):
    role = "airdrop"
    def __init__(self, calendar_provider, cadence_hours=6): ...
    def analyze(self, symbol, provider) -> Signal:
        ev = calendar_provider.event_for(symbol)  # claim_date, supply_inflation_pct, ...
        # --- Strategy A: claim-window VETO ---
        if ev and -7 <= ev.days_to_claim <= 7:
            return Signal(
                symbol, source="airdrop", direction="bearish",
                strength=-0.4,                 # capped: robust pattern, idiosyncratic outcome
                confidence=0.5,
                rationale=f"Claim-date sell pressure: 50-85% sell w1; "
                          f"typical -20-40% drawdown. Supply shock {ev.supply_inflation_pct}%.",
                extras={"event": "claim_veto", "days_to_claim": ev.days_to_claim,
                        "window": "T-7d..T+7d", "veto_long": True,
                        "supply_inflation_pct": ev.supply_inflation_pct},
            )
        # --- Strategy B: post-washout accumulate ---
        if ev and 30 <= ev.days_since_claim <= 120 and ev.drawdown_from_claim <= -0.35:
            util = utility_score(symbol)      # dev activity, ecosystem, staking incentives
            if util >= THRESHOLD:              # gate out the bleeders; keep the TIA/BONK names
                return Signal(
                    symbol, source="airdrop", direction="bullish",
                    strength=+0.3,             # capped conviction; modulator, not primary alpha
                    confidence=0.35,
                    rationale=f"Post-claim washout exhausted (d{ev.days_since_claim}, "
                              f"{ev.drawdown_from_claim:.0%}); utility_score={util:.2f} passes.",
                    extras={"event": "post_claim_accumulate",
                            "days_since_claim": ev.days_since_claim,
                            "drawdown_from_claim": ev.drawdown_from_claim,
                            "utility_score": util},
                )
        return Signal(symbol, source="airdrop", direction="neutral",
                      strength=0.0, confidence=0.0, rationale="no airdrop event in range")
```
- **`source="airdrop"`** is a new source alongside market/sentiment/macro/arbitrage/yield/depth.
- **Confidence deliberately capped** (A: 0.5, B: 0.35) so `combine_signals` (`signals.py:73`) and `weighted_combine` (`signals.py:87`) treat A as a **strong veto** (bearish + veto_long flag honored by the executor) and B as a **gentle conviction modulator** until forward-validated.
- Default `source_weights["airdrop"] ≈ 0.7` until the reflection loop calibrates it.

### 5.2 Strategy C — yield sleeve (not a per-symbol Signal)

Strategy C is **fleet-level config + a cron job**, not an analyst signal. Describe it as:
```
# config: fleet-level yield allocation
kickstarter:
  enabled: true
  mx_commit: 100000            # FAQ §4 hard cap; NEVER split across accounts
  account: <single KYC'd MEXC account>
  eligibility_futures_tick: manual_one_time   # not automated futures
  received_token_disposition: sell_at_listing_open   # via web/Convert, non-API (13 §6 Tactic A)
```
Maps to the `"yield"` source when surfaced as a Signal on MX itself (low-strength bullish carry), but the operative control is the scheduler that commits MX each session and liquidates receipts.

### 5.3 Touch points (file:line)
| Change | Where |
|---|---|
| New calendar provider (scrape-free: consume MEXC Telegram `t.me/MEXC_OfficialAnnouncements` + DefiLlama/token.unlocks for non-MEXC claims) | new `rapana/data/airdrop_calendar.py` |
| New analyst | `rapana/agents/airdrop.py` (mirror `agents/market.py`) |
| Register source `"airdrop"` | `rapana/signals.py:21` (extend comment) |
| Executor honors `extras["veto_long"]` → suppress new longs in claim window | `rapana/execution.py` / risk gate (`03-risk-edge.md`) |
| Kickstarter scheduler (yield sleeve) | new `rapana/fleet/kickstarter.py` |
| Backtest before live sizing | MEXC free historical download (`10-mexc-listings.md` §6) |

---

## 6. Free calendar & data sources (all free, key-less)

| Need | Source | Cost |
|---|---|---|
| **MEXC Kickstarter sessions** (commit open, listing time, pool size, total committed) | Official Telegram `t.me/MEXC_OfficialAnnouncements` (MEXC-endorsed, `10` §3.3) + `mexc.com/announcements/all` | free |
| MEXC Kickstarter mechanics (eligibility, commit caps, risk-control warning) | [Kickstarter Event FAQ](https://www.mexc.co/learn/article/kickstarter-event-faq/1) | free |
| **Cross-ecosystem airdrop calendar** (claim dates, snapshots) | [DefiLlama Airdrops](https://defillama.com/airdrops) | free |
| **Token unlock / vesting schedule** (claim-equivalent supply shocks) | [token.unlocks.app](https://token.unlocks.app) | free |
| On-chain airdrop analytics (sell-through rates, wallet-emptying) | [Dune airdrop dashboards](https://dune.com/browse/dashboards?q=airdrop) | free |
| Post-claim OHLCV / trade-side / depth | `GET /api/v3/klines`, `/api/v3/depth`, `exchangeInfo` (official API) | free, no key |
| **Backtest data (2023-01-01 → now)** | `mexc.co/zh-CN/market-data-download` (klines + trades, all spot pairs) | free, no key |
| Airdrop economics reference | [onchaineconomics](https://www.onchaineconomics.io/guides/airdrop-economics), [chainscorelabs autopsy](https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure) | free |

---

## 7. Risk register (honest)

| Risk | Likelihood | Mitigation |
|---|---|---|
| **Fat right tail on the short/avoid side** ("graduate-to-Binance" names pump +300% despite claim overhang) | Med | Strategy A is a **VETO/avoid**, never a naked perp short on the retail sleeve; hard cap if any directional short via separate KYB path. |
| **TIA-style counterexample** (utility demand overwhelms dump) | Low–Med | Strategy B **gates on utility_score** (dev activity, ecosystem momentum, staking) — only accumulate the washed-out names with real demand. |
| **Pool crowding dilutes Kickstarter ROI** as total MX committed grows | High over time | Track per-session realized yield on the account; stop committing when rolling yield < threshold. |
| **Received tokens dump** (the irony) | Very high | **Sell-at-listing-open, non-API channel** — mandatory, non-negotiable. |
| **MX price drawdown** while committed | Med | Size MX with its own risk budget; Kickstarter is carry *on an existing* MX thesis, not a reason to buy MX. |
| **Risk-control halts (30027/30028)** on listing-open liquidation of receipts | Med | You are a *recipient* selling, not chasing; still avoid the first-tick chaos (±5 min blackout, `16` §5.1). |
| **Multi-account Kickstarter farming** | — (do not do) | FAQ §4 explicit tripwire; single account, ≤100,000 MX, one identity (`16` §5.1). |
| **Magnitudes are analyst-compiled, not peer-reviewed** | — | Backtest the MEXC realized distribution on free history before sizing (`10` §6). |

---

## 8. Sources (consolidated, fetched 2026-06-23)

- S1 — MEXC, "Kickstarter Event FAQ" (mechanics, commit caps, multi-account risk-control warning). https://www.mexc.co/learn/article/kickstarter-event-faq/1
- S2 — onchaineconomics, "The hidden economics of airdrops: who pays when tokens are 'free'?" (zero-cost-basis dump mechanics; Chainalysis 50% UNI week-1; ARB 60% week-1; ARB price path $1.40→<$0.90). https://www.onchaineconomics.io/guides/airdrop-economics
- S3 — chainscorelabs, "Airdrop Dilution: The Hidden Cost of Unearned Tokens" (ARB/OP/STRK/TIA comparative autopsy; ENS >60% immediate sell; JTO $150M; Blur >$1B; 5–20% supply inflation overnight; 40–70% first-month drop). https://chainscorelabs.com/blog/tokenomics-design-mechanics-and-incentives/token-emission-and-supply/the-unseen-cost-of-airdrops-dilution-and-sell-pressure
- S4 — Cryptonews / Gabriel Halm (IntoTheBlock), "70% of Airdropped Tokens Fail to Deliver Profits" (23-token sample, 7 positive; OP Oct-2024 5× wallet-emptying). https://cryptonews.com/exclusives/70-of-airdropped-tokens-fail-to-deliver-profits-heres-why/
- S5 — CCN, "Starknet Price Drops 60% In Two Days As Founders Dump" (STRK $4 → <$1.90 in 2d). https://www.ccn.com/analysis/starknet-price-drops-two-days-founders-dump-what-next-strk/
- S6 — bitzo, "JUP Trading Volume Surges Over 200% Ahead of Jupiter's January Airdrop" (pre-snapshot farming rally +12%, vol +200%). https://bitzo.com/2026/01/jup-trading-volume-surges-over-200-ahead-of-jupiters-january-airdrop
- S7 — CoinCentral, "Jupiter Exchange Rethinks JUP Buyback Plan, Slashes Airdrop Size" (JUPuary 700M→200M to ease sell pressure; JUP −89% from ATH despite $70M buyback). https://coincentral.com/jupiter-exchange-rethinks-jup-buyback-plan-slashes-airdrop-size/
- S8 — DefiLlama Airdrops (calendar). https://defillama.com/airdrops
- S9 — token.unlocks.app (unlock/vesting schedule). https://token.unlocks.app
- S10 — Dune airdrop dashboards (on-chain sell-through). https://dune.com/browse/dashboards?q=airdrop
- Cross-ref: `13-mexc-fees-promos.md` §4/§5.2/§6 (Kickstarter as MX real-yield, API exclusion from 0-fee spot); `16-mexc-tos-envelope.md` §5 (Safe Operating Envelope); `10-mexc-listings.md` §2/§6 (listing-event behavior, free historical download, risk-control halts 30027/30028).

---

## Summary (≤4 lines)

The post-claim dump is the most consistent event effect in crypto — recipients have zero cost basis, so **50–85% sell within 7 days** and median drawdown is **−20 to −40% in weeks 1–4** (ARB −87%, STRK −62%/−60%-in-2-days, OP −58% over 30d; ~70% of airdropped tokens never profit), while a **pre-snapshot farming rally** often precedes it (JUP +12%/vol +200%). The three ToS-safe MEXC edges are: **(A) VETO longs / defer entries into ±7d claim windows** (never a retail perp short — KYB-gated), **(B) accumulate washed-out names 30–120d post-claim gated on a utility score** (to catch TIA/BONK-style recoveries and skip the bleeders), and **(C) MX-Kickstarter as ~10–20% annualized uncorrelated carry** — ToS-safe by construction (single account, ≤100k MX, never split) but **only realized with sell-at-listing-open discipline** since the received tokens themselves dump. Backtest all magnitudes on MEXC's free historical download before sizing; wire A/B as a capped-confidence `"airdrop"` source and C as a fleet-level yield scheduler.
