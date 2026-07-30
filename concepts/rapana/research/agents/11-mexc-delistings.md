# Agent 11 — MEXC Delisting / Market-Closure Behavior: The Forced-Sell Edge

**Scope:** Non-standard, event-driven edge on MEXC. Low-frequency (event-triggered, not HFT). Built on a structural mechanism (forced close + withdrawal window), not indicators.
**Status of evidence:** Mechanism & timelines verified from MEXC's own announcements (Jun 2026). Price magnitudes are calibrated to the well-documented crypto-wide delisting literature (MEXC/Binance analog); they should be backfilled with venue-specific OHLCV before live capital.

---

## 1. The mechanism — why a forced sell-off is structurally guaranteed

MEXC's delisting announcements use **identical boilerplate across every futures delisting** (verbatim, observed in 8+ announcements Jun 10–23 2026):

> "MEXC will close all positions for the abovementioned trading pairs **at the fair price at the time of delisting**. All open orders … will be canceled upon delisting. Users are encouraged to … close any open positions before delisting to minimize risk."

Source: e.g. `mexc.com/announcements/article/delisting-of-podusdt-natusdt-and-faiusdt-usdt-m-perpetual-futures-pairs-jun-26-2026-13-…`, `…delisting-of-sato-ika-maga-upeg-surplus-asteroid1-testicle-and-adi-…`, `…delisting-of-wojakusdt-perpetual-futures-pair-jun-22-…`, `…delisting-of-sc-pyr-gods-and-orbs-…` — all at `https://www.mexc.com/announcements/delistings` (66 pages of historical delistings available for backtesting).

This creates **three compounding forced-sell forces**:

1. **Leveraged long unwind.** Perpetual longs must close before the timestamp. Closing a long = market sell of the notional. The bigger the OI on that pair, the harder the forced sell.
2. **Liquidity vacuum.** Market makers and passive liquidity withdraw ahead of the deadline (no reason to provide two-way quotes on a dying market). Spread blows out, depth thins → same sell flow moves price more.
3. **Panic cascade.** Spot holders see the futures/print-press discount and front-run the exit on spot. Self-fulfilling.

The result is the classic **announcement-day dump (minutes to hours)** followed by a **pre-close bleed (final 24–48h, negative basis)** as the last longs are squeezed out.

---

## 2. Empirical timeline patterns (from MEXC announcements)

MEXC runs **three distinct delisting regimes**. They behave very differently — conflating them is the #1 way to lose money on this edge.

### Regime A — Perpetual futures delisting (most frequent, cleanest signal)
Announcement → forced close. Window is **short and machine-parseable**.

| Event (announced → delist) | Window |
|---|---|
| POD/NAT/FAI (Jun 23 → Jun 26 13:00 UTC) | ~3 d |
| SATO/IKA/MAGA/UPEG/SURPLUS/ASTEROID1/TESTICLE/ADI (Jun 18 → Jun 23 07:00) | ~5 d |
| WOJAK (Jun 17 → Jun 22 07:00) | ~5 d |
| TONUSDT/TONUSDC/TONUSD1 (Jun 16 → Jun 23 08:00) | ~7 d (migration) |
| XION (Jun 15 → Jun 17 07:00) | ~2 d |
| SC/PYR/GODS/ORBS (Jun 10 → Jun 13 09:00) | ~3 d |

**Typical window: 2–7 days. Median ≈ 3–5 days.** Enough reaction time for a low-freq, human-in-the-loop trader. The *spot* pair often keeps trading during this window — that is where the discount arbitrage lives.

### Regime B — Spot / Meme+ zone delisting (withdrawal window = the edge)
Boilerplate (from `mexc-meme-17827791536167`, RAGEGUY/LO0P):
- **ST (special treatment) period first** (Jun 8 → Jun 11, 3-day flag).
- Trading closed at delist time.
- **Deposits closed immediately; withdrawals stay open ~30 days** (delist Jun 11 14:00 → withdrawal cutoff **Jul 11 14:00**).

This ~30-day withdrawal window is the single most exploitable structural feature on MEXC. During it:
- The token is a **hot potato**: no new buyers want to enter a market they can only exit by withdrawing on-chain.
- Selling pressure has nowhere to go but down within MEXC.
- Rational holders withdraw to another venue → MEXC price decouples *below* the cross-venue fair value.
- The discount **mechanically closes** when you withdraw and sell on Binance/OKX/Bybit/Uniswap.

### Regime C — Migration / compensated delisting (low-risk, structural)
- **Token migration** (TON→GRAM, 1:1): not a dump, a rename. Delisting is mechanical. *Do not* apply the forced-sell thesis here.
- **Compensated delisting** (CTXC, `delisting-of-cortex-ctxc-…`): MEXC converted balances to USDT at the **5-day average closing price** (Jun 11–15 avg = 0.0009127 USDT/CTXC), i.e. **MEXC eats the forced-sell risk**. Here the edge is *holding through delist* to capture the average-price floor — but these are rare and ad-hoc (cannot be predicted, only reacted to).

### Frequency (sizing the opportunity set)
- 66 pages of delisting announcements on file.
- In the visible ~16-day window (Jun 10–26 2026): **~10+ delisting events, 20+ tokens**, across futures + spot + Meme+.
- This is a **high-frequency event class** at the *announcement* level but each event is low-frequency to trade (one decision, days of window). Excellent fit for MEXC's retail restrictions.

---

## 3. Where the edges actually are

### Edge (a) — DEFENSIVE: avoid / flat-before-delist (high confidence, positive EV with near-zero risk)
**Thesis:** Any position held across a delisting announcement absorbs an asymmetric, predictable drawdown. Simply not being there is a free risk-adjusted return versus a naive buy-and-hold basket.
- Empirical pattern (crypto-wide delisting literature, MEXC is a sharper version due to thinner books): **announcement-window drop of −15% to −40%** on the venue within minutes-to-hours, with the deepest prints in the final 24h.
- **Implementation:** maintain a live delisting-calendar feed (see §5). Hard-rule: **flat or near-flat any token within 48h of a scheduled MEXC delist**, regardless of view. This is a *risk* trade, not an alpha trade.
- **Edge size:** small per event, but it's pure tail-risk avoidance. The value is in *not* being in WOJAK/XION/etc. when they get force-closed.

### Edge (b) — CONTRARIAN: buy the delisting dump on tokens that survive elsewhere (speculative, asymmetric)
**Thesis:** Forced selling is non-informational. If the token has liquid markets on ≥1 *other* major venue (Binance/OKX/Bybit/Kraken) **and** the delisting reason is *liquidity/quality* (not fraud/hack/regulatory), the announcement drop overshoots fair value. Post-delist, with the forced seller exhausted, price mean-reverts toward the cross-venue quote.
- **Calibrated expectation (industry-typical, backfill before sizing):**
  - Tokens surviving on ≥1 major venue: **recover 20–60% of the announcement drop within 2–4 weeks** (mix of dead-cat bounce + genuine revaluation).
  - Tokens with **no other listing**: trend to effective zero (untradeable, withdrawal-only → abandonment). **Avoid.**
  - Tokens delisted for **fraud / exploit / SEC-style action**: trend to ~zero regardless of other listings. **Avoid.**
- **The asymmetry is brutal in the bad case** (see §4). This edge is real but requires a *filter*, not just buying every dump.

### Edge (c) — STRUCTURAL: the withdrawal-window discount close (cleanest, most actionable)
**Thesis:** During MEXC's ~30-day spot/Meme+ withdrawal window, MEXC price trades at a discount to other venues because (i) only existing holders can sell, (ii) new buyers are locked in, (iii) exit requires on-chain withdrawal. **Buy on MEXC at the discount → withdraw on-chain → sell on venue B at fair value.** Discount captured mechanically.
- This is **not** a bet on the token's future; it's a *carry* trade on a structural market-microstructure inefficiency.
- Risk is operational, not directional: withdrawal delays, gas spikes, the receiving venue also halting, or the discount widening before you can exit.
- **Magnitude:** needs direct measurement, but the structural logic is airtight and the venue split is real. Expect discounts in the **5–25% range** for illiquid Meme+ tokens, narrower (2–8%) for larger caps.

---

## 4. Asymmetric risk — why (b) must be hard-capped

The delisting dump is asymmetric **against** the contrarian in the bad case:

- **Good case:** token survives elsewhere → recover 20–60% of the drop. Bounded upside (~+30–80% from the dump low).
- **Bad case:** token goes to effective zero → −100% from your buy price. **Unbounded loss, frequently realized.**
- Empirically, a large share of delisted tokens (especially Meme+ / low-cap / fraud-flagged) **never recover**. Buying the dump without a survival filter is a negative-EV lottery.

### Hard risk caps for the contrarian book (mandatory)
| Parameter | Value | Rationale |
|---|---|---|
| Max gross exposure to delist-contrarian book | **≤ 1% of fleet NAV** | Tail risk is total-loss; cap like a venture allocation |
| Max per-token size | **≤ 0.20% NAV** | Diversify across many small shots |
| Hard stop per token | **−40% from fill** | Forces exit before zero; honors fat tails |
| Time stop | **30 calendar days** | If no reversion by then, thesis is wrong |
| **Survival filter (all must pass)** | | |
| — Cross-venue listing | ≥1 of {Binance, OKX, Bybit, Kraken} with >$100k 24h vol | Ensures a real exit |
| — Delisting reason | Liquidity / quality / Meme+ cleanup ONLY | Exclude fraud/hack/regulatory |
| — No simultaneous delist on venue B | within 14 days | Contagion risk |
| — Spot only | No leveraged/perp exposure to delisted names | Forced-close risk |
| Max concurrent open contrarian positions | **5** | Limit correlation/batch-risk |

The defensive book (Edge a) and the structural book (Edge c) carry **no directional tail risk** and can be sized larger; only Edge (b) is capped at 1% NAV.

---

## 5. Detection feed — free, low-freq, ToS-clean

MEXC publishes delistings through several channels. **None require scraping protected pages in a ToS-hostile way:**

1. **Official announcements page** — `https://www.mexc.com/announcements/delistings` (public, paginated, 66 pages of history). Polling every 5–15 min is well within "public API" norms.
2. **Official Telegram channel** — `t.me/MEXC_OfficialAnnouncements` (referenced in MEXC's own listing notices as the early-signal source). Telegram Bot API + channel ID = push notifications, sub-minute latency, no scraping.
3. **MEXC API** — MEXC exposes listing/delisting via its public REST endpoints; check `/api/v3/exchangeInfo` (spot symbol status flips) and the contract API's instrument list for perp removals. Status changes are authoritative and free.
4. **Cross-venue confirmation** — CoinGecko / CoinMarketCap listing-status fields, plus each target venue's own `/exchangeInfo` to verify the token is *actually* still tradeable elsewhere before firing a contrarian order.

**Recommended minimal stack:**
- A 10-min poller on the delistings page + Telegram push as the fast lane.
- A normalizer that extracts: `token`, `pair`, `delist_type` (futures / spot / meme+ / migration / compensated), `delist_timestamp_utc`, `reason_text`.
- A classifier: migration/compensated → regime C (skip or hold-through); futures/spot/meme+ → regime A/B (apply strategies).
- A cross-venue liveness check (Edge b filter) before any contrarian order is allowed.

Latency target: **seconds to a few minutes** is plenty. This is not an HFT race; the window is days. The first-mover advantage is in *risk avoidance* (Edge a) and *filling the discount before it closes* (Edge c), not in beating another bot by milliseconds.

---

## 6. Recommended posture for Rapana

| Strategy | Role | Sizing | Confidence |
|---|---|---|---|
| **(a) Defensive flat-before-delist** | Risk overlay on the whole fleet | Mandatory rule, no capital | **High** — mechanism is mechanical |
| **(c) Withdrawal-window discount capture** | Carry/structural alpha | Up to 2–3% NAV gross, per-token ≤0.5% | **Medium-high** — logic airtight, magnitudes TBD |
| **(b) Contrarian dump-buy on survivors** | Asymmetric lottery ticket | **≤1% NAV gross, hard-capped** | **Medium** — real edge, brutal tails, needs filter |

**Sequence to productionize:**
1. Build the detection feed + classifier (§5). Backfill all 66 pages of history → label each delist by regime and outcome.
2. Ship Edge (a) immediately as a risk rule. Near-zero build cost, immediate tail protection.
3. Measure Edge (c) discounts on the next ~10 spot/Meme+ delistings paper-traded before risking capital.
4. Only after (c) is validated, allocate the 1% contrarian sleeve with all §4 caps enforced in code (not in discretion).

---

## 7. Open questions / next research

- Direct backtest: pull OHLCV for every MEXC-delisted token (last 12 months) and measure (i) announcement-window drawdown distribution, (ii) 30-day post-delist return split by *survives-elsewhere* vs *not*, (iii) MEXC-vs-Binance basis during withdrawal windows.
- Does MEXC's "fair price" forced close (perpetuals) leave a measurable fingerprint on the *underlying spot* in the final hour? (Latency-arb flavor, but retail-feasible if the move is slow.)
- Correlation of delisting clusters with broader risk-off regimes (do many delistings at once = contagion → avoid Edge b entirely?).

---

### Key sources
- MEXC delistings index (primary): `https://www.mexc.com/announcements/delistings`
- Forced-close boilerplate (verbatim, multiple): futures delisting articles Jun 2026
- Withdrawal-window structure: `mexc-meme-17827791536167` (RAGEGUY/LO0P, Jun 11 delist → Jul 11 withdrawal cutoff)
- Compensated delisting precedent: `delisting-of-cortex-ctxc-and-compensation-arrangement-17827791536278` (5-day avg price conversion)
- Migration regime: `delisting-of-tonusdt-tonusdc-…` (TON→GRAM 1:1)
- Official early-signal channel: `t.me/MEXC_OfficialAnnouncements`
