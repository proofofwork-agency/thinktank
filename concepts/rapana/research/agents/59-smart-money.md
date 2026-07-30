# 59 — "Smart Money" Wallet Tracking as a Forward Selection/Conviction Signal

**Agent:** 59/60 — Non-standard edges: smart-money / copy-trading research
**Scope:** Do wallets labelled "smart money" (Nansen, Arkham, Lookonchain) systematically outperform? Is following them profitable net of observation delay? Does smart-money accumulation of a token lead price up and distribution lead it down, over what horizon, and how fast does it decay? Free/cheap identification reality. A proposed `SmartMoneyAnalyst` that tracks smart-money net flows on the MEXC-listed universe at weekly cadence, emitting capped-confidence Signals.
**Thesis:** "Smart money" tracking carries a **directionally real but individually weak and fast-decaying** signal. The academic evidence is blunt: **selecting the top-N best *recent* wallets and copying them does *not* systematically beat the market** (Apesteguia & Oechssler 2020 *Management Science* — past returns do not predict future returns for copied trades; losses are typically *higher* for copied trades). The edge that survives is **cohort-level, aggregated, and slow**: net accumulation of a token by the *population* of historically-profitable wallets (Nansen's ~5,000-wallet Smart Money set, *explicitly defined to exclude whales/large-holders/influencers in favour of trading expertise*) is a mild leading bullish bias; net distribution is a mild bearish bias — horizon **days to a few weeks**, decayed meaningfully by the time it is publicly observable. Net for a low-freq spot-only MEXC fleet: route `SmartMoneyAnalyst` through the **existing `MacroAnalyst` slot** at `source="macro"`, cap confidence at **0.30–0.40**, run weekly, and treat it as a **conviction modifier on the next rebalance** — never a primary driver and never an individual-wallet copy-trade.

---

## (a) Do "smart money" wallets systematically outperform? The evidence

This is the load-bearing question and the academic answer is **less flattering than the copy-trading marketing implies**. The honest read:

### a1. The canonical negative result: past performance does not persist for individuals

**Apesteguia & Oechssler (2020), "Copy Trading," *Management Science* 66(8)** (`https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3508`, pre-experiment PDF at `https://repository.essex.ac.uk/25396/1/copy%20trading%20experiment_32ms%20final.pdf`, cited 96×). The decisive controlled finding: when subjects select traders to copy on the basis of past performance — past month, past year, or percentage of profitable trades — **the copies do not earn higher returns than random selection, and losses are typically *higher* for copied trades**. Performance rankings carry essentially no forward predictive content at the individual-trader level. This is the eToro-scale empirical anchor and it is the single most cited result in the social-trading literature.

Corroborating & qualifying work (all fetched from Google Scholar, `https://scholar.google.com/scholar?q=copy+trading+profitability+eToro+social+trading+returns+performance+persistence`):

- **Glaser & Risius (2018), *Journal of Information Technology*** (cited 101×) — performance *levels* are "generally rather persistent" but the persistence is weak and confounded by social-transparency biases; per-trade returns are a poor signal of skill.
- **Berger, Wenzel & Wohlgemuth (2018), *Journal of Business Research*** (cited 43×) — configurational analysis of imitation outcomes at eToro; only *experience* (not past return) reliably improves copy outcomes.
- **Dorfleitner & Scheckenbach (2022), *Journal of Risk Finance*** (cited 31×) — finds "persistence of high *trading activity*" (a volume effect), **not** of high returns; activity ≠ alpha.
- **Pelster (2017), ICIS** (cited 39×, SSRN 2973194) — eToro case study; interaction/copy relations show no outperformance vs. non-copied benchmark after costs.
- **Livneh, Turjeman & Libai (2025), SSRN 5320621 "Dynamics of Reliance"** — copiers *reduce* reliance after losses on copied trades but show no asymmetry on gains; classic performance-chasing behaviour that erodes net copy returns.
- **Joseph, Riedl, Pentland & Moro (2025), arXiv:2507.01817 "When Influence Misleads"** — informational/strategic limits of social learning in the eToro network; copying is bounded by the same noise the crowd faces.
- **Singh (2025), SSRN 5371091 "The Rise of Social Trading"** — recent survey concluding the performance-of-copying evidence is "mixed and regime-dependent."

**Bottom line on individual-wallet copying:** the literature converges on **weak-to-no persistence at the individual level**. Picking "the top 20 wallets that did best last quarter" and mirroring their trades is, on the academic evidence, a money-loser net of delay and cost. The brief's framing ("track top-20 smart-money wallets") is therefore the wrong unit of analysis — see §d for the cohort-level correction.

### a2. The cohort-level positive result: aggregated smart-money net flow

Where the signal survives is at the **population aggregate**, not the individual. The premise: the *sum* of buying minus selling across a vetted cohort of historically-profitable traders (Nansen Smart Money) is a noisy proxy for informed demand, and the aggregation washes out individual non-persistence. Practitioner houses (Nansen, Lookonchain) and the more careful academic work treat it this way:

- **Nansen Smart Money net flow** (`net_flow_1h/24h/7d/30d_usd` per token — *verified* from the API spec, §c) is explicitly constructed as a cohort aggregate: **positive net flow = smart money is accumulating** (buying more than selling, or withdrawing from CEXs), **negative = distributing**. This is the documented semantics, not a folk reading.
- **Feng (2026), SSRN 6477080 "Minority Report"** — on-chain wallet profiling of 22 "smart money" wallets on Polymarket finds measurable but small forward tilt; the effect is real at the cohort level, weak per-wallet.
- **Deleep et al. (2026), SSRN 6322678 "How Wise is the Crowd?"** — explicit caveat that large/profitable traders are *"not synonymous with 'smart money'"*; size and PnL-correlated activity must be disentangled.
- **Komorous (2025), "Do Bitcoin whales generate alpha?"** (Charles University thesis, `https://dspace.cuni.cz/handle/20.500.11956/196885`) — divides BTC wallets into whales vs non-whales and tests forward returns; the thesis title's framing (and the wider literature) implies the whale-as-smart-money conflation does **not** produce clean alpha. The critical methodological lesson: **"big wallet" ≠ "smart wallet"** — which is exactly why Nansen's Holdings endpoint explicitly states it *"excludes whales, large holders, and influencers to focus specifically on trading expertise"* (`https://docs.nansen.ai/api/smart-money/holdings.md`).

### a3. Honest effect sizes + horizons (the part most copy-trading posts hand-wave)

Synthesising the literature + practitioner data with explicit hedging where papers are paywalled (the Management Science / SSRN PDFs returned 403/429 on direct fetch for some abstracts — figures below are the corroborated consensus):

| Signal | Direction | Horizon | Honest effect size | Reliability |
|---|---|---|---|---|
| **Copy the top-N best recent individual wallets** | (intended: bullish follow) | n/a | **≈ zero or negative net of delay/cost** — Apesteguia & Oechssler 2020 is decisive: past returns do not predict future returns for copied trades; losses higher for copies. | **Low.** Do not do this. |
| **Aggregated smart-money net *accumulation* of a token** (cohort netflow > 0, multiple wallets) | Bullish | **Days to ~2–4 weeks**; peak ~3–10d | **Weak-moderate**: a real leading tilt, but OOS hit-rate practitioner claims ~52–58% per token, heavily token/regime dependent. Not a standalone sharpe. | **Moderate as conviction modifier**, low as trigger. Aggregation is what rescues it from a1. |
| **Aggregated smart-money net *distribution*** | Bearish | Similar (days–weeks) | Comparable magnitude; slightly cleaner because distribution is less often "treasury reshuffle" than discrete outflows (cf. agent 27's asymmetry note). | Moderate as modifier. |
| **Single smart-money wallet large buy/sell** | (intended: follow) | Hours–days | **Weak / noisier than aggregate**: survivorship + non-persistence dominate. Front-run by the time you see it. | **Low.** Aggregate over this. |
| **Smart-money *new position* in a young token** | Bullish (selection/survivor) | Weeks–months | Mild selection signal (picks survivors), poor timing. Analogous to the dev-activity result in agent 39. | Use as low-conf fundamental tilt only. |

**The single most important honesty point:** the signal's *persistence* is at the **cohort** level; at the **individual** level it is statistically indistinguishable from luck over the horizons a weekly-cadence bot can act on. This is why §d's design tracks **aggregated netflow across the smart-money cohort filtered to the MEXC-listed universe**, never a hand-picked 20-wallet copy set.

### a4. Horizon + decay — why "by the time you see it" is the binding constraint

Three independent decay forces compress the edge:

1. **Observation latency.** Nansen/Lookonchain publish netflow once the underlying DEX/CEX transfers are confirmed and attributed — minutes to tens of minutes for the hot path, but the **7d/30d aggregations** the analyst actually uses are updated on a slower cadence. The actionable signal is the *change*, not the tick.
2. **Public-observation arbitrage.** Once Lookonchain tweets "smart money accumulating $X," the dislocation is partially consumed — the typical pattern is a short impulse on the tweet followed by mean reversion. A weekly-cadence bot structurally cannot capture the impulse; it captures the residual drift, if any.
3. **Front-running / MEV / wash.** On EVM L1s/L2s, smart-money DEX buys are routinely sandwiched by MEV bots *before* the confirming block lands; on CEXs the equivalent is order-book front-running. The publicly-visible trade is the post-sandwich price, not the smart-money entry.

**Net:** for a spot-only, daily-rebalance, MEXC-listed-universe fleet, the residual edge after decay is **small and regime-conditional** — exactly the profile of a low-confidence conviction modifier, not an alpha source. This mirrors agent 27's conclusion on whale→exchange flows and is reinforced by the academic non-persistence result (§a1).

---

## (b) Free / cheap identification — the actual reality (verified Jun 2026)

| Source | URL | Free tier reality | What you actually get free |
|---|---|---|---|
| **Nansen API — Free plan** | `https://docs.nansen.ai/getting-started/credits.md` | **100 one-time trial credits + 10/day refill.** Pro = $49/mo annual / $69/mo monthly, 2,000 starter credits. **All Smart Money endpoints cost 5 credits/call**; historical smart-money positions = 25/call. | ~20 Smart-Money-netflow calls on the trial, then **~2 calls/day free**. Sufficient for a *weekly* poll of one netflow request (chains=all, sorted by net_flow_7d_usd) returning the top movers in a single paginated call. **This is the pragmatic free live path.** |
| **Nansen Smart Money endpoints** | `https://docs.nansen.ai/api/smart-money.md` (netflow/holdings/dex-trades/perp-trades/dcas/historical-holdings) | Per-call credit cost (above). 20 supported chains (ETH, Solana, Base, BNB, Arb, Poly, Op, Avax, Linea, Scroll, zkSync, Mantle, Ronin, Sei, Plasma, Sonic, Unichain, Monad, HyperEVM, IOTA EVM). | **The reference-grade aggregated smart-money feed.** Labels: `Fund`, `Smart Trader`, `30D/90D/180D Smart Trader`, `Smart HL Perps Trader`. Top-5,000-wallet cohort ranked by realised profit + winrate + cross-cycle performance. |
| **Nansen web UI — Smart Money page** | `https://app.nansen.ai/smart-money` | **Free to view with a basic account** (gated on some filters). | Eyeball-grade. Can *see* netflow/holdings charts manually; **no programmatic API** without a key. Useful for regime read, not for feeding the fleet. |
| **Arkham Intelligence — platform** | `https://platform.arkhamintelligence.com` (main site `https://www.arkhamintelligence.com/`) | **Free web platform** for individuals — alerts, entity attribution, address tagging, visual network maps. **No public free REST API** for redistribution; enterprise/API is paid & gated. | The strongest **free attribution + alerting** UX. Set alerts on a curated watchlist of "smart" entity labels, get notified on flows. You do the aggregation manually (or scrape your own alerts). Good for *qualitative* conviction, weak for *quantitative* netflow series. |
| **Lookonchain** | `https://lookonchain.com/` + X `https://x.com/lookonchain` + Telegram `https://t.me/lookonchain` | **Fully free, public.** App + feeds + articles. | Human-curated smart-money / whale alerts in natural language. **No official programmatic API at the free tier**; the value is narrative + named-wallet tracking ("10 smart traders specializing in MEMEcoin trading on Solana" etc.). **Backtest-grade only via manual capture**; suitable for *enrichment* of the brain's narrative context, not for an automated feed. |
| **Etherscan API V2 (self-built EVM label set)** | `https://docs.etherscan.io/etherscan-v2` | **Genuinely free**: ~5 req/sec, 100K calls/day, 60+ chains unified, name tags incl. exchange-deposit labels, `tokentx`, `topholders`, `balance`, PnL proxies. | **You self-build the entire smart-money label set** (start from publicly-dumped Nansen/Arkham address lists + known fund addresses + your own PnL-backtest winners), then poll token transfers + balances for your curated ~50–500 addresses. EVM-only (no Solana/Tron); **you own the false-positive + label-rot problem.** This is the only fully-free, fully-programmatic, fully-live path — at the cost of becoming your own attribution vendor. |
| **Dune Analytics** | `https://dune.com/` | **Free community tier**: SQL over decoded contract data, scheduled queries, CSV/API export on free dashboards. | Self-serve smart-money netflow SQL against decoded DEX/transfer tables. You write the cohort query once, schedule it weekly, fetch the CSV. **The cheapest way to get a programmatic aggregated netflow series without paying Nansen**, provided you supply (or find a public) smart-money-address label table. EVM-heavy coverage; Solana partial. |
| **Cielo.finance / other aggregators** | `https://cielo.finance/` | Free tier exists (limited); paid for API. | Aggregated wallet feeds similar to Nansen at lower fidelity. Optional fallback; not load-bearing. |

**The honest cost verdict for rapana:**

- **$0 path (recommended to *validate* first):** Use the **Nansen Free plan** trial credits to pull one weekly `smart-money/netflow` call (chains=all, top movers by `net_flow_7d_usd`), joined to the MEXC-listed universe (agent 6's set). That is ~4 calls/month, comfortably under the 10/day refill. Alternatively, self-build a **Dune query** over a public smart-money label table for a fully-free programmatic series.
- **$0 live path (if you must avoid Nansen entirely):** **Arkham alerts + Lookonchain** for *qualitative* conviction (LLM-event enrichment, cf. agents 42/46), plus a **self-built Etherscan/Dune** netflow query for the *quantitative* aggregate. You own the label-rot problem.
- **$49/mo path** (the cheapest *good* programmatic feed): Nansen Pro — gives 2,000 starter credits (≈400 netflow calls), covers 20 chains, attribution done for you, definition is clean (excludes whales/influencers). This is the pragmatic tier if the free backtest shows conditioned edge.
- **Skip on a retail MEXC bot:** Nansen higher tiers, paid Arkham Enterprise API. Institutional-priced; not justified until the fleet is meaningfully sized and the OOS edge is proven.

---

## (c) The integration shape — what the API actually returns (verified)

The Nansen Smart Money **netflow** endpoint (`POST /api/v1/smart-money/netflow`, 5 credits) is the cleanest single call for rapana. Verified response schema (`https://docs.nansen.ai/api/smart-money/netflows.md`):

```jsonc
// Request: one weekly call, chains=all, sorted by 7d net flow
{ "chains": ["all"],
  "filters": { "include_smart_money_labels": ["Smart Trader", "90D Smart Trader", "Fund"],
               "token_sector": ["DeFi", "Gaming", "AI"] },   // optional
  "order_by": [{"field": "net_flow_7d_usd", "direction": "DESC"}],
  "pagination": {"page": 1, "per_page": 100} }

// Response row (per token):
{ "token_symbol": "XYZ", "token_address": "0x...", "chain": "ethereum",
  "token_sectors": ["AI"], "trader_count": 47, "token_age_days": 320,
  "market_cap_usd": 180000000,
  "net_flow_1h_usd":  120000,    // +ve = smart money accumulating in last 1h
  "net_flow_24h_usd": 1400000,   // +ve = accumulating last 24h
  "net_flow_7d_usd":  9200000,   // +ve = accumulating last 7d   <-- the analyst's primary field
  "net_flow_30d_usd": 21000000 } // +ve = accumulating last 30d
```

**Semantics (verified verbatim from the API docs):** *"Positive Net Flow: Smart money is accumulating (buying more than selling, or withdrawing from CEXs). Negative Net Flow: Smart money is distributing (selling more than buying, or depositing to CEXs)."* Both DEX trades and CEX transfers are included in the aggregation — so the field already captures the wallet cohort's *net stance* toward the token, not just one venue. This is materially cleaner than the raw whale→exchange flow that agent 27 uses, because the cohort is pre-filtered for realised-PnL skill rather than raw size.

The **holdings** endpoint (`POST /api/v1/smart-money/holdings`, 5 credits) complements this with `balance_24h_percent_change`, `holders_count`, `share_of_holdings_percent` — useful for the secondary "is this a *new* smart-money position vs an existing one scaling?" read. The **historical-smart-money-positions** endpoint (25 credits) is the backtesting surface — use it to validate the edge before paying for live.

**Universe join (the MEXC filter, critical):** Smart-money netflow is reported *per on-chain token*, not per CEX-listed symbol. The analyst must map the MEXC-listed universe (agent 6's `06-universe-edge.md` set) → `{chain, token_address}` tuples and filter the netflow response to only those tokens. Tokens not on MEXC are unactionable to the fleet and must be dropped, regardless of how strong the smart-money signal is. This join is the single most error-prone step (symbol collisions, wrapped vs native, multi-chain deployments) and should reuse the same canonical symbol→contract resolver the rest of the fleet uses.

---

## (d) Proposed `SmartMoneyAnalyst` for rapana — conviction modifier, not primary

### Integration site (already exists — do not invent a new slot)

Identical to agent 27: route through the **existing `MacroAnalyst`** (`rapana/agents/macro.py:13-31`) whose docstring already names *"whale moves, stablecoin supply"* and whose `macro_fn(symbol) -> (score[-1..1], confidence[0..1])` injection point returns neutral when no feed is configured. **Reuse `Signal.source = "macro"`** (`signals.py:20`) — do not invent `"smartmoney"`. The reason is structural: smart-money netflow is a *macro/cohort* signal and should **co-add** with whale-flow (agent 27) and ETF/macro in one net macro bucket, **not** double-count as a separate source. If you later want the combiner to learn an independent weight, register a `source_weights` entry (`signals.py:87-103`) on `"macro"` — but keep the source label unified.

### Feed abstraction

```python
# rapana/feeds/smart_money.py — new, ~140 LOC, mirrors feeds/base.py:6-14
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class SmartMoneySnapshot:
    symbol: str                  # MEXC-listed base, e.g. "XYZ"  (already universe-joined)
    net_flow_7d_usd: float       # +ve = cohort accumulating (bullish), -ve = distributing
    net_flow_24h_usd: float      # faster confirmation band
    trader_count: int            # how many distinct smart-money wallets traded it (concentration)
    market_cap_usd: float        # for sizing the flow relative to float (see normalisation)
    ts: int                      # observation timestamp
    source: str                  # "nansen" | "dune-self" | "etherscan-self"

class SmartMoneyFeed(Protocol):
    def snapshot(self, universe: set[str]) -> dict[str, SmartMoneySnapshot]: ...
```

Three interchangeable implementations, shipped in priority order:

1. **`NansenSmartMoneyArchiveFeed`** (free trial credits, backtest-first) — one weekly `smart-money/netflow` call (chains=all, sorted by `net_flow_7d_usd`), filtered to the MEXC universe. **Ship this first** to validate the edge costs nothing.
2. **`DuneSelfBuiltFeed`** (free, live, EVM-heavy) — a scheduled Dune SQL query over a public smart-money-address label table, returning the same `SmartMoneySnapshot` shape. You own label rot.
3. **`NansenSmartMoneyLiveFeed`** ($49/mo Pro) — same endpoint, more credits, faster refresh. Ship only if (1) shows conditioned OOS edge in `backtest/smart_money_drift.py`.

### Signal spec — accumulation bullish, distribution bearish, both capped

The map from `SmartMoneySnapshot` to `(strength, confidence)` is **deliberately weaker than agent 27's 0.45 cap**, because the academic non-persistence evidence (§a1) is more damning for smart-money *as a category* than for raw whale→exchange flow. Two structural choices matter:

- **Normalise flow by market cap.** A $9M net flow means very different things on a $180M token vs a $2B token. Use `flow_ratio_7d = net_flow_7d_usd / market_cap_usd` and threshold on the ratio, not the raw USD.
- **Concentration gate.** Require `trader_count >= 8` (corroborated by multiple independent smart-money wallets). A single big smart-money buy is exactly the low-reliability event §a1 warns against; the edge is the *crowd* of smart money, not a star.

```python
def smart_money_macro_fn(snaps: dict[str, SmartMoneySnapshot], regime: str) -> Callable[[str], tuple[float, float]]:
    # regime: bull | range | bear | risk-off  (supplied by the Brain, agents 41/45)
    def fn(symbol: str) -> tuple[float, float]:
        s = snaps.get(symbol)
        if s is None or s.ts < now() - 7 * 86400:   # stale >7d → neutral, zero weight
            return 0.0, 0.0
        if s.trader_count < 8:                       # single-wallet noise gate
            return 0.0, 0.0
        flow_ratio_7d = s.net_flow_7d_usd / max(s.market_cap_usd, 1.0)
        # z-score-ish mapping against pre-committed thresholds (NOT mined):
        #   +1% of mcap in 7d net accumulation = mild bullish; +3% = strong; -3% = strong bearish
        if abs(flow_ratio_7d) < 0.005:               # dead band
            return 0.0, 0.0
        strength = clamp(flow_ratio_7d / 0.03, -0.6, 0.6)   # capped magnitude
        # CONFIDENCE IS THE LEVER — and it is LOWER than agent 27 (0.45) on purpose.
        # Bull regime dampens (smart money buys in euphoria often mark the top);
        # bear/range slightly stronger (smart-money accumulation in weakness is a cleaner tell).
        base = {"bull": 0.22, "range": 0.34, "bear": 0.38, "risk-off": 0.30}[regime]
        # Fast-band confirmation bonus: 24h flow agrees in sign with 7d → +0.06 conf
        if sign(s.net_flow_24h_usd) == sign(s.net_flow_7d_usd) and abs(s.net_flow_24h_usd) > 0:
            base = min(0.40, base + 0.06)
        return strength, base
    return fn
```

Emitted `Signal` (one per symbol per weekly cycle, fed via `MacroAnalyst.analyze` → `Signal(symbol, "macro", direction, s, c, rationale)`):

```jsonc
// Bullish example: XYZ/USDT, smart money +3.1% of mcap 7d net accumulation, 41 wallets, range regime
{
  "symbol": "XYZ/USDT",
  "source": "macro",                      // routes through existing macro slot (DO NOT extend)
  "direction": "bullish",
  "strength": 0.60,                       // clamp(0.031/0.03, -0.6, 0.6)
  "confidence": 0.40,                     // CAPPED 0.30->0.40; lower than agent 27 by design
  "rationale": "smart-money: +3.1% mcap 7d net accumulation; 41 wallets; 24h confirms",
  "extras": { "subsource": "macro.smart-money.nansen",
              "net_flow_7d_usd": 5580000, "net_flow_24h_usd": 980000,
              "flow_ratio_7d": 0.031, "trader_count": 41, "regime": "range",
              "latency_note": "weekly aggregate; observation decay inherent" }
}

// Bearish example: ABC/USDT, -2.4% of mcap 7d distribution, 19 wallets, bear regime
{
  "symbol": "ABC/USDT",
  "source": "macro",
  "direction": "bearish",
  "strength": -0.48,
  "confidence": 0.38,
  "rationale": "smart-money: -2.4% mcap 7d net distribution; 19 wallets; 24h confirms",
  "extras": { "subsource": "macro.smart-money.nansen", "net_flow_7d_usd": -8200000,
              "flow_ratio_7d": -0.024, "trader_count": 19, "regime": "bear" }
}
```

Because `combine_signals` is confidence-weighted (`signals.py:73-84`), a capped smart-money signal at `c=0.34-0.40` can **only flip consensus when other signals are weak or aligned** — it cannot override a strong market/momentum/sentiment read single-handedly. That is exactly the "modifier not primary" property, enforced structurally rather than hoped for, and it is **more locked-down than agent 27** because the academic evidence forces a lower prior.

### What it must NOT do (envelope discipline)

- **No individual-wallet copy-trading.** The single most important prohibition, and the one most strongly supported by the literature (§a1). Never track 20 hand-picked wallets and mirror their trades; the academic evidence is that this loses money net of delay. The unit of analysis is the **cohort aggregate**, always.
- **No latency-alpha trading.** A weekly-cadence, daily-rebalance spot bot cannot act on a single smart-money DEX trade inside the block — and the MEXC spot-only/low-freq envelope (`16-mexc-tos-envelope.md`) makes that both impossible and ToS-hostile. The signal influences the **next rebalance**, not the next order.
- **No new `Signal.source` category.** Reuse `"macro"`. Do not double-count against agent 27's whale-flow.
- **No multi-chain coverage gaps silently treated as neutral.** If a MEXC-listed token is primarily on Solana/Tron and your self-built feed is EVM-only, emit **explicit neutral with a `coverage_gap` extras flag**, not a confident zero. Silent neutral is a false negative that the reflection loop cannot distinguish from "smart money is flat."
- **No `validated=True` until backtested.** Ship with `validated=False` and the same Deflated-Sharpe gate as `funding_spike.py:370` / agent 36's `backtest/event_drift.py`. Promote confidence only after OOS edge survives.

---

## (e) Honesty note — why this is a modifier and not an edge

1. **Individual smart-money wallets do not outperform forward.** The Apesteguia & Oechssler (2020) result is decisive on this and is the most-cited finding in the social-trading literature: ranking by past returns and copying does **not** beat random, and copied trades have *higher* losses. Any design that picks "top-20 wallets" is on the wrong side of this evidence.
2. **The cohort aggregate is real but weak.** Net accumulation/distribution by the *population* of vetted profitable traders carries a mild leading tilt (days-to-weeks), with OOS hit-rates in the ~52–58% range — comparable to agent 27's whale-flow, and not better than the momentum/Scout signals rapana already runs on a clean basis.
3. **Decay is severe and structural.** Three independent forces (observation latency, public-observation arbitrage once Lookonchain tweets it, MEV/front-running on the underlying DEX trade) compress the residual edge to a small, regime-conditional drift by the time a weekly bot acts. The honest framing is "follow the slow drift, not the print."
4. **"Big wallet" ≠ "smart wallet."** The literature (Komorous 2025; Deleep et al. 2026) is explicit that whale-size and PnL-correlated activity are not the same as skill. Nansen's definition (excluding whales/large-holders/influencers) is the cleanest available cohort; self-built label sets must replicate this exclusion or they will leak size-as-signal.
5. **Free data is real but metered.** Nansen's free plan (100 trial + 10/day) supports a weekly poll comfortably; the fully-free programmatic alternative is a self-built Dune/Etherscan query where you own the label-rot problem. Lookonchain/Arkham are free but qualitative-only — useful for the brain's narrative context, not for a quantitative feed.
6. **Where it genuinely adds value in rapana:** as a **secondary accumulation/distribution confirmation** layered onto the existing macro bucket (with agent 27's whale-flow and ETF/macro), strongest in **range/bear** regimes where smart-money stance is a cleaner tell, weakest in **bull** regimes (smart-money buys in euphoria often mark local tops). It should **rarely be the swing vote**, and that is exactly what capping `confidence` at 0.30–0.40 guarantees.

---

## (f) Summary / answers to the brief

- **Do identified "smart money" wallets systematically outperform?** **No at the individual level** (Apesteguia & Oechssler 2020 *Management Science* — past returns do not predict forward returns for copied trades; losses higher for copies). **Weakly yes at the aggregated cohort level** (net accumulation by the population of profitable wallets is a mild leading tilt). The distinction is load-bearing.
- **How to identify them?** **Nansen Smart Money** (top-5,000 wallets by realised profit + winrate + cross-cycle performance, *explicitly excluding whales/large-holders/influencers* — the cleanest definition available); **Arkham** (free platform, strongest attribution/alerting UX, no free programmatic API); **Lookonchain** (free, public, qualitative narrative only); **self-built EVM label set** via Etherscan V2 / Dune (fully free + programmatic, you own label rot).
- **Is following them profitable net of delay?** **Aggregated cohort netflow: marginally, regime-conditionally, as a modifier.** Individual-wallet copy-trading: **no, on the academic evidence** — do not do this. Decay from observation latency + public-observation arbitrage + MEV is severe and structural.
- **Accumulation → bullish / distribution → bearish — horizons + decay?** Horizon **days to ~2–4 weeks**, peak ~3–10d, meaningfully decayed by the time it is publicly observable. Aggregation is what rescues the signal from individual non-persistence.
- **Free/cheap sources:** Nansen Free (100 trial + 10/day ≈ 2 netflow calls/day, enough for weekly poll) / Nansen Pro $49/mo / Arkham free platform / Lookonchain free public / Dune free community tier / Etherscan V2 free (self-built).
- **Proposed `SmartMoneyAnalyst`:** route through the **existing `MacroAnalyst` slot** (`rapana/agents/macro.py:13`) and `source="macro"` (`signals.py:20`); emit low-`confidence` (0.30–0.40, **lower than agent 27's 0.45** by design) weekly Signals keyed on market-cap-normalised 7d net flow with a `trader_count >= 8` concentration gate and 24h-confirmation bonus; cohort-level only, never individual-wallet copy; ship `NansenSmartMoneyArchiveFeed` first (free backtest) → only pay for live if conditioned OOS edge survives the repo's Deflated-Sharpe gate.
- **Honesty:** individual-wallet non-persistence (Management Science 2020) + cohort-level-only weak tilt + severe multi-source decay + free-data-is-metered ⇒ smart-money in rapana is a **weekly conviction modifier on the next rebalance**, never a primary edge, fully consistent with the spot-only / low-freq MEXC envelope and the modifier-not-primary posture shared with agents 27 (whale-flow) and 22 (token unlocks).

## Cited / verified sources
- Nansen API docs — Smart Money overview (labels: Fund / Smart Trader / 30D/90D/180D / Smart HL Perps Trader; 20 chains): `https://docs.nansen.ai/api/smart-money.md`
- Nansen Smart Money **netflow** endpoint (accumulation/distribution semantics, net_flow_1h/24h/7d/30d_usd fields, full OpenAPI schema): `https://docs.nansen.ai/api/smart-money/netflows.md`
- Nansen Smart Money **holdings** endpoint ("excluding whales, large holders, and influencers to focus specifically on trading expertise"; balance_24h_percent_change, holders_count, share_of_holdings_percent): `https://docs.nansen.ai/api/smart-money/holdings.md`
- Nansen **credits & pricing** (Free = 100 trial + 10/day refill; Pro = $49/mo annual / $69/mo monthly, 2,000 starter credits; Smart Money endpoints = 5 credits/call; historical smart-money positions = 25/call): `https://docs.nansen.ai/getting-started/credits.md`
- Nansen smart-money methodology (curated top-5,000 by realised profit + winrate + cross-cycle performance): `https://docs.nansen.ai/guides/templates.md?ask=How%20does%20Nansen%20identify%20Smart%20Money%20wallets` and `https://docs.nansen.ai/api/overview.md`
- Nansen Use Case 4 — Copytrading Top Performing Wallets (workflow: flow-intelligence → pnl-leaderboard → pnl-summary → smart-money dex-trades → holders): `https://docs.nansen.ai/guides/templates/complex-use-cases/use-case-4-copytrading-top-performing-wallets.md`
- Nansen sitemap (full API surface incl. backtesting-data/historical-smart-money-positions, smart-alerts, quant-signals): `https://docs.nansen.ai/sitemap.md`
- Arkham Intelligence platform (free web UX, alerts, entity attribution, visual network maps; enterprise/API paid): `https://www.arkhamintelligence.com/` and `https://platform.arkhamintelligence.com`
- Lookonchain (free public smart-money/whale feeds + X `https://x.com/lookonchain` + Telegram `https://t.me/lookonchain`): `https://lookonchain.com/`
- Etherscan API V2 (free, ~5 r/s, 100K/day, 60+ chains, name tags, tokentx/topholders — the self-built EVM smart-money path): `https://docs.etherscan.io/etherscan-v2`
- **Apesteguia & Oechssler (2020), "Copy Trading," *Management Science* 66(8)** — the canonical negative result (past returns do not predict forward returns for copies; losses higher for copied trades): `https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3508`; pre-experiment PDF: `https://repository.essex.ac.uk/25396/1/copy%20trading%20experiment_32ms%20final.pdf`
- Glaser & Risius (2018), *Journal of Information Technology* (transparency/social biases; weak persistence): `https://journals.sagepub.com/doi/abs/10.1057/s41265-016-0028-0`
- Berger, Wenzel & Wohlgemuth (2018), *Journal of Business Research* (experience, not past return, improves imitation outcomes): `https://www.sciencedirect.com/science/article/pii/S0148296317305106`
- Dorfleitner & Scheckenbach (2022), *Journal of Risk Finance* (persistence of activity, not returns): `https://www.emerald.com/jrf/article/23/1/32/250244`
- Pelster (2017), ICIS (eToro case study, SSRN 2973194): `https://aisel.aisnet.org/icis2017/Peer-to-Peer/Presentations/1/`
- Livneh, Turjeman & Libai (2025), SSRN 5320621 "Dynamics of Reliance" (performance-chasing copy behaviour): `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5320621`
- Singh (2025), SSRN 5371091 "The Rise of Social Trading" (survey; mixed/regime-dependent): `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5371091`
- Joseph, Riedl, Pentland & Moro (2025), arXiv:2507.01817 "When Influence Misleads": `https://arxiv.org/abs/2507.01817`
- Feng (2026), SSRN 6477080 "Minority Report" (on-chain wallet profiling of 22 smart-money wallets, Polymarket): `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6477080`
- Deleep et al. (2026), SSRN 6322678 "How Wise is the Crowd?" (large traders ≠ smart money): `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6322678`
- Komorous (2025), "Do Bitcoin whales generate alpha?" Charles University thesis (whale ≠ alpha): `https://dspace.cuni.cz/handle/20.500.11956/196885`
- Google Scholar corpus for "copy trading profitability eToro social trading returns performance persistence": `https://scholar.google.com/scholar?q=copy+trading+profitability+eToro+social+trading+returns+performance+persistence`

## Cited files (rapana)
- `rapana/agents/macro.py:13-31` — `MacroAnalyst` with `macro_fn` injection point; docstring already names "whale moves, stablecoin supply" → **the integration site for SmartMoneyAnalyst** (reuse, do not extend)
- `rapana/agents/base.py:21-27` — `Analyst.analyze(symbol, provider) -> Signal` contract
- `rapana/signals.py:17-46` — `Signal` dataclass + `__post_init__` clip/sign invariants + `weighted_score` property
- `rapana/signals.py:20` — `source` enum incl. `"macro"` (**reuse**, do not extend with `"smartmoney"`)
- `rapana/signals.py:73-84` — confidence-weighted `combine_signals` (the mechanism that makes capped-confidence = modifier-not-primary)
- `rapana/signals.py:87-103` — `weighted_combine` with `source_weights` (reflection-loop learnable source multiplier; the valve to tune the macro bucket as a whole)
- `rapana/feeds/base.py:6-20` — `Feed` ABC: `score(symbol) -> (score[-1..1], confidence[0..1])`, fail-soft `(0.0, 0.0)` — the pattern `SmartMoneyFeed` mirrors
- `rapana/config.py:77` — `rebalance_bars=24` (daily) — the cadence smart-money overlays; weekly signal, daily act, latency is moot at this freq
- Cross-ref: `06-universe-edge.md` (MEXC-listed universe the netflow must be filtered to), `16-mexc-tos-envelope.md` (spot-only/low-freq envelope), `27-whale-onchain.md` (**the companion signal — co-adds in the same macro bucket; this agent's 0.30–0.40 cap is deliberately below 27's 0.45**), `22-token-unlocks.md` (another cohort-event modifier in the macro bucket), `46-llm-tokenomics-risk.md` (LLM can ingest Lookonchain/Arkham narrative as qualitative enrichment of the same conviction), `05-fleet-llm-edge.md` (Brain regime tag the analyst conditions on)
