# 28 — Exchange Reserve / Net-Flow Dynamics as a Macro Regime Signal

**Agent:** 28/60 · **Scope:** aggregate exchange BTC/ETH balance (reserve) and net-flow
(inflow − outflow), plus stablecoin reserves, as a **slow, regime-level macro overlay**
that classifies risk-on / risk-off and **scales the whole fleet's max exposure**.
**Hard constraint (load-bearing):** spot-only, low-frequency, no-arb, no cross-venue
execution (`RESEARCH-SYNTHESIS.md:90,108`; `research/agents/16-mexc-tos-envelope.md`,
`18-mexc-premium.md:4`). This is a **read-only on-chain/market-data signal** consumed by a
fleet-wide sizing layer — it never trades a second leg, never chases latency. It is the
opposite end of the spectrum from the per-symbol tactical edges (notes 08–18): slow,
regime-level, market-wide.

All repo citations are `file:line`. External claims are URL-cited in §f.

---

## (a) What the metrics are, and where the free data lives

### The three core series

| Metric | Definition (verbatim from source) | Source / URL |
|---|---|---|
| **Exchange Balance (Reserve)** | "The total amount of coins held on exchange addresses" — derived from continually-updated labeled exchange addresses + clustering heuristics. A **mutable** series: established history is stable, recent points revise as labels update. | Glassnode Distribution endpoints · https://docs.glassnode.com/basic-api/endpoints/distribution.md |
| **Exchange Netflow** | `netflow = inflow_volume − outflow_volume` (USD or NATIVE). Positive netflow = coins arriving on exchanges (intended sell-side); negative = coins leaving (accumulation / cold storage). | Glassnode Transactions · https://docs.glassnode.com/basic-api/endpoints/transactions.md · `GET /v1/metrics/transactions/transfers_volume_exchanges_net` |
| **Stablecoin Supply Ratio (SSR)** | `SSR = MarketCap(BTC) / MarketCap(all stablecoins)`. **Low SSR → high stablecoin buying power over BTC** (proxy for fiat dry powder); high SSR → buying power thin. | Schultze-Kraft & Shirakashi (Nov 2019), "Stablecoins' Buying Power over Bitcoin" · https://insights.glassnode.com/stablecoins-buying-power-over-bitcoin/ |

### What the data actually is (and what it isn't)
Glassnode's own Exchange Data Transparency Notice is explicit and should temper any
naive read of these series (https://docs.glassnode.com/further-information/exchange-data-transparency-notice.md):

- "Exchange metrics strictly refers to **on-chain metrics** — those that monitor exchange balances and movements by identifying, labeling, and observing blockchain addresses and wallets owned by centralized exchanges. Metrics stemming from off-chain data ... such as futures or spot volume, are excluded."
- Accuracy is **validated against Proof-of-Reserve disclosures** (Binance, Bitfinex, BitMEX, Bybit, Crypto.com, Deribit, Gemini, Huobi, OKX, KuCoin publish PoR; Coinbase/Kraken/Gate/Poloniex/Bithumb do **not** — their balances are estimates only and "can largely be considered as lower bounds of the true balance").
- Data is **limited to BTC and ETH** (on-chain labels for those two chains). For altcoins the exchange-reserve signal does not exist at this quality — only BTC/ETH aggregate balance is a clean, market-wide regime input. **This is exactly why it is a macro overlay, not a per-altcoin signal.**
- "Reported exchange balances may undergo **retrospective revisions**. Automatic or manual identification and addition of addresses ... can recalibrate the balance ... Preliminary data manifestations, such as a significant inflow or outflow, ought to be approached with caution."
- **Use point-in-time data for backtesting** (`/data/point-in-time-metrics.md`); otherwise you trade on revisions and manufacture fake alpha.

**Implication for Rapana:** treat these as **daily, regime-level** inputs only. Never react to a single day's netflow print; the series can be revised. Trend over rolling windows (7/30/90-day) is the usable information. This is the inverse of the funding/orderbook signals in notes 12–14 — it is *deliberately* slow.

### Free / freemium sources (no paid tier required for a regime read)
| Source | Coverage | Free? | Notes |
|---|---|---|---|
| **Glassnode Studio** (web) | BTC + ETH exchange balance, netflow, SSR, Realized Cap | Free tier (limited history, daily) | https://studio.glassnode.com — visual, but the free tier is enough to read regime direction. API needs a key (free tier exists, rate-limited). |
| **CryptoQuant community** (web) | BTC Exchange Reserve, Exchange Netflow Total, Stablecoin Supply Ratio | Free community dashboard | https://cryptoquant.com/asset/btc/chart/exchange-flows/exchange-reserve and `.../exchange-netflow-total` — JS-rendered but the daily values are readable; community tier is free. |
| **Coinglass** | Exchange reserves (BTC/ETH), stablecoin market cap, long/short | Free | https://www.coinglass.com/ — aggregator; reserves + stablecoin sections are public. |
| **DefiLlama** | Stablecoin market cap (aggregate + per-chain), 24h USD in/out of CEX via `cex-flows` | Free, no key, JSON API | https://defillama.com/stablecoins and https://defillama.com/cex-flows — the cleanest free programmatic source for stablecoin supply + CEX netflow. **Primary recommendation for the automated feed.** |

**Recommended primary feed for Rapana:** **DefiLlama** (`/stablecoins`, `/cex-flows`) for
the programmatic, no-key, JSON regime read — it gives aggregate CEX netflow and stablecoin
supply without any auth or KYC surface. Cross-check daily against the Glassnode/CryptoQuant
community dashboards (manual). DefiLlama is the lowest-friction, ToS-cleanest choice and
already consistent with the repo's "no new secrets" posture (`research/agents/08-mexc-client-edge.md`).

---

## (b) Does declining exchange reserve predict price rises? Honest evidence

### The directional claim (well-supported qualitatively)
The "supply shock" thesis is the single most-repeated on-chain narrative in crypto: coins
leaving exchange addresses → less liquid supply available for sale → price rise. The
reverse — coins arriving on exchanges → intended distribution → price drop. **Both
directions are real and consistent with basic microstructure**, and are the operating
assumption of every on-chain desk (CryptoQuant and Glassnode research use this framing
throughout their weekly notes). The mechanism is clean:

- **Netflow → available float:** exchange balances are the immediately sellable supply.
  A persistent drain mechanically tightens spot supply, so the same demand bids price up
  more (this is the *static* version of the S&P/CoinAPI "thinner books → larger moves"
  result already cited in `research/agents/18-mexc-premium.md:31-32`, applied at market scale).
- **Netflow → intent signal:** coins moved *to* exchanges are, empirically,
  sell-intended (Kraken/Coinbase deposits precede sells); coins moved *off* are
  accumulation / cold-storage / self-custody. Makarov & Schoar (2020, JFE 135:293–319)
  document that exchange inflows spike **during stress and momentum breaks** — i.e. the
  flow-to-exchange signal is most informative at regime turns, exactly where it is useful.
- **Realized Cap as the aggregate flow summary:** Glassnode's "Week On-chain" (Week 24,
  2026, "A Market in Repair") uses **90-day Realized Cap change** as the canonical
  regime classifier: *"Realized Cap contracting at the cycle scale confirms the bear read
  ... placing the market in what can be characterized as a deep bear where both valuation
  discount and capital flow trajectory are in agreement. The conditions required before a
  credible transition to a pre-bull phase ... are specific and measurable: a reclaim of the
  True Market Mean ... and Realized Cap turning positive on the 90-day horizon."* This is
  the industry-standard read of aggregate net flow.

### Magnitude / horizon / regime-dependence (the honest part)
Peer-reviewed academic work that *quantifies* the exchange-reserve → return relationship
in a way you could drop into a Sharpe calculation is **thin**. The honest, defensible
statements are:

| Claim | Evidence quality | Practical read |
|---|---|---|
| **Direction is right on average:** declining reserve co-occurs with bull regimes, rising with bear/distribution regimes | High (industry consensus + mechanism; Makarov & Schoar 2020 for the inflow-during-stress sub-claim) | Treat as a **regime filter**, not a return forecaster |
| **Effect horizon is days-to-weeks, not hours:** reserve trends are slow-moving; the predictive content is in multi-week z-scores, not daily prints | High (Glassnode explicitly uses 7/30/90-day SMAs; "preliminary data ... ought to be approached with caution") | Daily netflow noise ≫ signal; only smoothed trends are tradeable |
| **Series revisions can erase apparent alpha:** using current (revised) exchange-balance history to backtest manufactures fake predictability | High (Glassnode Transparency Notice; only Point-in-Time metrics are immutable) | **Mandatory**: only backtest on point-in-time data, or via walk-forward from snapshots you actually stored |
| **Signal is most valuable at regime turns, not in trends:** the biggest reserve outflows in history cluster at cycle lows (accumulation); biggest inflows at cycle tops (distribution) | High (Glassnode cycle work; CryptoQuant's "supply shock" framing) | Asymmetric optionality: better at catching *regime shifts* than *trend continuation* |
| **Effect is regime-dependent on itself:** during a bear, reserve outflows can persist for months while price keeps falling (capitulation/self-custody flight); the signal can be **early and wrong** for weeks | Medium (anecdotal but recurring; 2022 LUNA/FTX episodes) | Never use netflow as a *standalone* timing signal — only as an exposure scalar |

**Bottom line on the edge:** it is real but **slow, lag-prone, and best as a regime
filter that scales exposure rather than a directional trade trigger.** This is precisely
why the brief asks for a `RegimeAnalyst` that *modulates* sizing — that is the only
honest way to use this data. Anyone selling "exchange netflow predicts next-day returns"
is overfitting to revised history.

### Stablecoin reserves → buying power
The same directional logic, cleaner because stablecoin supply is less revision-prone (it's
mint/burn events on-chain, not address-label estimates):

- **Rising stablecoin supply (esp. USDT minting) → rising buying power → bullish bias.**
  Schultze-Kraft & Shirakashi (2019) frame SSR exactly this way: *"when SSR is low, the
  current stablecoin supply has more buying power to purchase BTC"* and note that Tether
  issuance historically moved BTC price the majority of the time (cited therein via AMBCrypto).
- **Falling stablecoin supply → redemption / dry powder draining → bearish bias.**
  Large USDT burns on Ethereum/Tron are a documented risk-off signature.
- SSR is a **level** metric (ratio), best used as a **regime percentile / z-score**, not
  an absolute trigger. Combine with the reserve trend for confirmation: *both* declining
  BTC reserve *and* rising stablecoin supply = strong risk-on setup; *both* rising BTC
  reserve *and* falling stablecoin supply = strong risk-off.

---

## (c) Macro regime strategy — `RegimeAnalyst` + fleet exposure overlay

### Design principle: two distinct levers, both wired

The existing `MacroAnalyst` (`rapana/agents/macro.py:13-31`) already takes a
`macro_fn(symbol) -> (score, confidence)` callable and emits `source="macro"`. But that
only feeds the **per-symbol** combine — it is one vote among many for each token. The
*regime* ask is bigger: a **fleet-wide** exposure scalar that sits on top of the whole
sizing layer. So the proposal has **two components** that share one feed:

```
                 ┌──────────────────────────────────────────────────────────┐
   DefiLlama     │  RegimeNetflowFeed  (rapana/feeds/regime_netflow.py)       │
   Glassnode ──▶ │   • btc_reserve_30d_zscore()                              │
   (free tier)   │   • stablecoin_supply_30d_change_pct()                    │
                 │   • realized_cap_90d_change_pct()  (if available)         │
                 │   • regime() -> ("risk_on"|"neutral"|"risk_off", score)   │
                 └───────────────┬───────────────────────┬──────────────────┘
                                 │                       │
                  ┌──────────────▼─────────┐   ┌─────────▼───────────────┐
                  │  Path A (per-symbol):   │   │  Path B (fleet overlay): │
                  │  existing MacroAnalyst  │   │  RegimeExposureOverlay   │
                  │  source="macro" Signal  │   │   scales RiskPolicy      │
                  │  → weighted_combine     │   │   max_total_exposure_pct │
                  └─────────────────────────┘   └──────────────────────────┘
```

**Path A** is the cheap, do-first step: it gives the regime read its **own
`ReflectionMemory` bucket** (`rapana/fleet/memory.py:114-121`) so the fleet learns whether
the macro analyst is actually adding value, independently of the other sources. This
matches the contract analysis in `research/agents/01-strategy-edge.md:45-53` — new-data
edge belongs in an `Analyst`, not a `Strategy` (which would be folded into
`source="market"` and lose its identity).

**Path B** is the real macro overlay: a fleet-level scalar that multiplies
`RiskPolicy.max_total_exposure_pct` (currently consumed at `risk/guardrails.py:220-224`).
This is the lever that *"cuts to defensive when risk-off, full size when risk-on."* It is
the genuinely non-standard addition; Path A alone would just be a fourth analyst vote.

### Regime classification rule (deterministic, no LLM)
A simple, auditable scoring on smoothed z-scores. Keep it transparent so the journal can
explain *why* exposure was cut.

```python
# pseudo — the actual feed returns these; RegimeExposureOverlay maps to a scalar
def regime() -> tuple[str, float]:
    # each input is a z-score or % over a trailing window; sign-convention:
    #   reserve_drain   = -btc_reserve_30d_zscore()   # +ve = coins leaving = bullish
    #   stablecoin_lift =  stablecoin_supply_30d_change_pct()  # +ve = minting = bullish
    #   rcap_lift       =  realized_cap_90d_change_pct()       # +ve = capital entering
    composite = (
        0.45 * reserve_drain          # the headline signal
      + 0.35 * stablecoin_lift        # buying-power confirmation
      + 0.20 * rcap_lift              # aggregate flow confirmation (if available)
    )
    # hysteresis: require the composite to cross thresholds WITH N-day persistence
    # to avoid regime-flip whipsaw on noisy daily prints
    if composite >  +1.0 and persisted(>= +1.0, days=3):  return "risk_on",   composite
    if composite <  -1.0 and persisted(<= -1.0, days=3):  return "risk_off",  composite
    return "neutral", composite
```

Key design choices, each load-bearing:
- **Weighted composite, not single-metric.** Reserve trend alone whipsaws; confirming it
  with stablecoin supply and Realized-Cap change filters false signals (e.g. a reserve
  drain during a stablecoin redemption is *not* risk-on — it's self-custody flight under
  stress, which Makarov & Schoar show is bearish).
- **Hysteresis / persistence gate (3 days).** Daily exchange-balance prints are noisy and
  revised; Glassnode's own guidance is to smooth over 7/30/90-day windows. A regime
  change must *persist* before exposure moves — this prevents the overlay from chopping
  the fleet's gross on every wobble.
- **All inputs are slow (30d / 90d).** The overlay changes state on the order of
  *weeks*, not hours. This is by design and is exactly what makes it compatible with the
  MEXC low-frequency envelope (`research/agents/16-mexc-tos-envelope.md`).

### Exposure modulation (Path B — the fleet overlay)
Map the regime label to a scalar on `max_total_exposure_pct` and (optionally)
`max_position_pct` in `RiskPolicy` (`risk/guardrails.py:28-38`). The scalar is applied at
the `PreTradeChecker` construction / refresh, not per-order, so it scales the *whole
fleet's* capacity:

| Regime | `exposure_scalar` | Effect on `max_total_exposure_pct` (default policy) | Effect on `max_position_pct` |
|---|---|---|---|
| **risk_on** | **1.00** | full (e.g. 0.60 → 0.60) | full |
| **neutral** | **0.65** | defensive-ish (0.60 → 0.39) | 0.80× |
| **risk_off** | **0.30** | defensive (0.60 → 0.18) | 0.50× |

(The exact scalars are config; the point is the *monotone* mapping. They never go to zero
— even in risk-off the fleet stays in the market at reduced size, because the regime
signal lags and a hard exit would realize the lag as a loss.)

**Why scale the cap, not force flat:** the signal is slow and revised. Cutting to 30% gross
in risk-off preserves optionality to be wrong; forcing flat would convert a *regime filter*
into a *market-timing bet*, which this data does not support. The reflection memory
(`fleet/memory.py:114`) will tell you over time whether the overlay is adding value; if it
isn't, the scalar compresses toward 1.0 automatically (Bayesian shrinkage on the macro
bucket's hit rate).

### How it composes with the per-symbol tactical edges
The two paths are **complementary, not redundant**:
- **Per-symbol edges** (funding, premium, listing-detection, orderbook — notes 08–18) are
  *fast* and *tactical*: they pick *what* to trade and *when*. They run on the MEXC
  envelope at bar cadence.
- **Regime overlay** (this note) is *slow* and *strategic*: it sets *how big* the whole
  book can be. It runs daily, changes state weekly.

The clean separation mirrors the brain-can't-move-orders safety design already in
`portfolio_manager.py:46-51` (*"narrative research informs humans; deterministic math moves
capital"*): the regime read is *deterministic math* on free on-chain data, applied as a
scalar on the deterministic `PreTradeChecker`. No LLM in the loop, no override of the hard
veto (`risk_manager.py:7-12`).

---

## (d) Signal spec — `RegimeAnalyst` (source="macro") + `RegimeExposureOverlay`

A new `Feed` + the existing `MacroAnalyst` (Path A) **plus** a new `RegimeExposureOverlay`
(Path B). Drops in with zero core rewrite; both are additive.

### Fit with the existing contract (why this is cheap)
- **`Feed` ABC** (`rapana/feeds/base.py:6-14`): `score(symbol) -> (score[-1..1], confidence[0..1])`, fail-soft `(0.0,0.0)`. The regime feed returns the **same score for every symbol** (it's a market-wide signal) — that's fine; `weighted_combine` (`signals.py:87-104`) treats each symbol independently and the reflection memory learns one macro bucket.
- **`Analyst` ABC** (`agents/base.py:26`, consumed at `fleet/orchestrator.py:91-95`): the *existing* `MacroAnalyst` (`agents/macro.py:13-31`) already accepts a `macro_fn` and emits `source="macro"`. **No new analyst class needed for Path A** — just inject the feed's callable. This is the lowest-friction wiring possible.
- **`Signal` currency** (`signals.py:17-46`): sign-auto-corrected, clamped, free `extras: dict` — stash `regime_label`, `reserve_drain_z`, `stablecoin_lift_pct`, `rcap_lift_pct`, `persistence_days` for journal/audit.
- **`RiskPolicy`** (`risk/guardrails.py:17-38`): `from_settings` is a classmethod; the overlay recomputes `max_total_exposure_pct` / `max_position_pct` from a base policy × scalar on each daily regime refresh. `PreTradeChecker.check` (`risk/guardrails.py:217-233`) is unchanged — it just sees a rescaled policy.

### Components

**1. `RegimeNetflowFeed(Feed)`** — `rapana/feeds/regime_netflow.py` (mirror `feeds/base.py` + DefiLlama client)
- Construct with a `defillama_fn` callable (or a tiny `httpx` client) hitting `/stablecoins` (aggregate stablecoin mcap + 24h change) and `/cex-flows` (aggregate CEX netflow). Cache 24h; refresh once daily.
- Inputs (all free, no key, JSON):
  - `btc_reserve_proxy`: DefiLlama `cex-flows` rolling 30d net (or the BTC balance proxy it exposes). If Glassnode free-tier API key is available, prefer `/v1/metrics/distribution/balance_exchanges?a=BTC` for the clean reserve series.
  - `stablecoin_supply`: DefiLlama `/stablecoins` total mcap (USDT+USDC+DAI+...), 30d % change.
  - `rcap_lift` (optional): Glassnode Realized Cap 90d change if available on the free tier; else drop this term and renormalize weights to 0.57 / 0.43.
- `regime() -> (label, composite)` as in §c; `score(symbol) -> (s, c)` returns the composite (clamped to [-1,1]) for every symbol, with `confidence` rising in `persistence_days` (low confidence on a fresh flip, high after a week of stability).

**2. Wiring Path A (per-symbol vote)** — `fleet/orchestrator.py:94` already constructs `MacroAnalyst()`; change it to `MacroAnalyst(macro_fn=regime_feed.score)` and the macro bucket goes live with its own reflection-memory weight. Zero new class.

**3. `RegimeExposureOverlay`** — `rapana/risk/regime_overlay.py` (new, ~40 lines)
- Holds a base `RiskPolicy` (the `from_settings` one) and the regime feed.
- `current_policy() -> RiskPolicy`: returns a rescaled `RiskPolicy` by the scalar table in §c. Called once per day (or per fleet cycle, cheaply) and handed to the `PreTradeChecker` constructor / a setter.
- Emits a `DecisionLedger` entry (`journal/ledger.py`) on every regime change for audit: *why* exposure was cut/raised, with the underlying z-scores. This is the same transparency pattern as the existing `risk_veto` ledger writes (`risk/guardrails.py:237-238`).
- **Never overrides `max_daily_loss_pct`, `kill_switch`, or `circuit_breaker`** — those stay at base policy always. The overlay only scales the *exposure* caps, never the *loss* caps. This preserves the Flash-Crash proofing mandated by `research/agents/03-risk-edge.md`.

### Execution-side notes
- The overlay is **cadence-clean**: it changes at most a few times a month. It never adds order throughput, never touches the `OrderRateLimiter` (`risk/guardrails.py:65-101`), never creates a pattern MEXC's risk engine could flag (`research/agents/16-mexc-tos-envelope.md`). It just makes the *next* batch of proposed orders smaller/larger.
- A risk-off regime naturally trims the book over time as positions are sold into strength (the per-symbol edges still drive exits) and fewer/larger buys are approved. It does *not* force liquidation — see §c ("never go to zero").
- All inputs are public on-chain / market data read over HTTPS. No exchange auth, no keys, no KYB, no new secrets. Strictly consistent with the repo's security posture (`AGENTS.md`, `research/agents/08-mexc-client-edge.md`).

---

## (e) Honest limits and failure modes (be explicit)

1. **Lag.** Reserve trends are slow; the signal turns *after* the move has started. Expect
   the regime call to be ~1–3 weeks behind the actual top/bottom. This is acceptable for an
   *exposure scalar* (you're sizing the next month, not timing the next bar) and
   unacceptable for a *timing trigger*. The design above only uses it as a scalar — do not
   be tempted to also fire directional trades off it.
2. **Revisions.** Exchange-balance history is mutable (Glassnode Transparency Notice §3).
   Any backtest must use point-in-time snapshots or it is fiction. The live feed should
   store its own daily snapshots (`data/`) so future backtests are honest.
3. **Altcoin-blindness.** Exchange-reserve labels are BTC/ETH-only. The overlay is a
   *market-wide* regime read, applied uniformly to every symbol the fleet trades. It does
   not — cannot — tell you anything per-altcoin. (Per-altcoin flow signals are a different,
   harder problem; not this note.)
4. **Self-custody flight false-positive.** A reserve drain during a stablecoin redemption
   is risk-off dressed as risk-on. The composite weights stablecoin supply *against*
   reserve drain precisely to catch this; if they diverge, confidence drops and the regime
   stays "neutral." This is the single most important guardrail — do not remove it.
5. **Regime-dependence on itself.** In a deep bear, reserve can keep draining while price
   keeps falling (capitulation). The Realized-Cap term (aggregate *value* of flow, not just
   coin count) is the correction: in true risk-off, Realized Cap contracts even as
   coin-count reserve might be doing anything. The composite needs both.
6. **Data-source risk.** DefiLlama is community-maintained; if it degrades, fall back to
   Glassnode free-tier or CryptoQuant community reads. The feed must fail-soft to
   `("neutral", 0.0)` — never block the fleet on a missing macro print.

---

## (f) Sources (verified, load-bearing)

- **Glassnode — Exchange Data Transparency Notice** (methodology, PoR table, revision caveats) — https://docs.glassnode.com/further-information/exchange-data-transparency-notice.md · quotes in §a.
- **Glassnode — Distribution endpoints** (Exchange Balance, Exchange Reliance Ratio) — https://docs.glassnode.com/basic-api/endpoints/distribution.md.
- **Glassnode — Transactions endpoints** (`transfers_volume_exchanges_net`, inflow/outflow/netflow) — https://docs.glassnode.com/basic-api/endpoints/transactions.md.
- **Schultze-Kraft R., Shirakashi R. (Nov 2019), "Stablecoins' Buying Power over Bitcoin"** (SSR definition, stablecoin-as-fiat-proxy, buying-power framing) — https://insights.glassnode.com/stablecoins-buying-power-over-bitcoin/.
- **Glassnode — SSR metric guide** (low SSR = high buying power) — https://docs.glassnode.com/further-information/metric-guides/stablecoin/ssr-stablecoin-supply-ratio.md.
- **Glassnode Research — "A Market in Repair" (Week On-chain, Week 24, 2026)** (Realized Cap 90d change as canonical regime classifier; STH-MVRV breakeven; spot orderbook depth imbalance as regime signal; capital-flow-trajectory framing) — https://research.glassnode.com/the-week-onchain-week-24-2026/.
- **Makarov I., Schoar A. (2020), "Trading and Arbitrage in Cryptocurrency Markets,"** *J. Financial Economics* 135:293–319 — exchange inflows spike during stress/momentum; cross-venue flow dynamics under regime change (also cited in `research/agents/18-mexc-premium.md:28`).
- **CryptoQuant — Exchange Reserve & Exchange Netflow (Total) charts (BTC)** — https://cryptoquant.com/asset/btc/chart/exchange-flows/exchange-reserve · https://cryptoquant.com/asset/btc/chart/exchange-flows/exchange-netflow-total (community tier, free, JS-rendered).
- **Coinglass — exchange reserves & stablecoin aggregates** (free public aggregator) — https://www.coinglass.com/.
- **DefiLlama — Stablecoins & CEX Flows** (free, no-key JSON APIs; recommended primary feed) — https://defillama.com/stablecoins · https://defillama.com/cex-flows.
- **Repo priors** — `rapana/agents/macro.py:13-31` (existing `MacroAnalyst` + `macro_fn` injection point); `rapana/risk/guardrails.py:17-233` (`RiskPolicy`, `PreTradeChecker`, exposure caps); `rapana/fleet/memory.py:114-121` (per-source reflection memory); `research/agents/01-strategy-edge.md:45-53` (Analyst vs Strategy contract); `research/agents/03-risk-edge.md` (loss-cap / veto invariants preserved by the overlay); `research/agents/16-mexc-tos-envelope.md` & `18-mexc-premium.md` (MEXC spot-only / low-freq / no-arb envelope).

---

## Bottom line

Exchange reserve / net-flow dynamics are a **real but slow, regime-level** signal:
declining BTC reserve + rising stablecoin supply co-occur with bull regimes (supply
shock + dry powder), and the reverse with bear/distribution regimes — but the effect
operates over **weeks, is regime-dependent on itself, and the underlying series is
revised**, so it is honest **only as an exposure scalar, never a timing trigger.** Wire
it as (A) the existing `MacroAnalyst` fed by a free DefiLlama/Glassnode `RegimeNetflowFeed`
(its own learnable `source="macro"` bucket), and (B) a deterministic
`RegimeExposureOverlay` that rescales `RiskPolicy.max_total_exposure_pct` daily —
risk-on → full size, neutral → ~0.65×, risk-off → ~0.30×, with hysteresis and a
stablecoin-vs-reserve divergence guard. Both are additive, no core rewrite, no new
secrets, fully inside the MEXC spot/low-freq envelope.
