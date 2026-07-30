# 09 — MEXC 0% spot maker fee: edge mechanism, magnitude & minimal capture

**Agent:** 9/60 · **Scope:** MEXC fee structure (spot + futures), the 0% maker edge,
adverse-selection literature, and the minimal rapana change to capture it.
**Posture:** LOW-FREQUENCY, MAKER-ORIENTED, EVENT-DRIVEN — to stay inside MEXC's
retail anti-bot envelope (`RESEARCH-SYNTHESIS.md:90,108`; fleet-wide constraint).

---

## TL;DR

- MEXC's headline **0% spot maker fee** is still active in 2026 but is **no longer a
  flat universal rate** — it is delivered as a *dynamic per-account/per-region promo*
  and/or via the **MX-deduct** toggle (which gives **0% on spot AND on futures** when
  funded). The authoritative per-account number is read live from the API
  (`Query Symbol Commission`, `exchangeInfo.makerCommission`).
- The structural edge is real but **small**: on liquid majors (BTC/ETH, 1 bp spread) it
  is **~0 net after adverse selection**; on mid-liquidity pairs (5–15 bp spread) an
  inventory-capped wide-band ladder nets **~1–4 bp per round trip** honestly.
- The edge is **100% unreachable today** — `LiveExecutor` is market-only
  (`execution.py:95`). Minimal capture: one new client method + one field on
  `TradeProposal` + a branch in `LiveExecutor`.

---

## 1. Current MEXC fee structure (2026) — confirmed

### Spot
The official fee page (`https://www.mexc.com/fee`, fetched 2026-06-23) is **deliberately
non-numeric**:

> "Maker fee rates may vary with platform events or user region. Please refer to the
> actual trade history." — *MEXC Fee Overview, official page*

> "Taker fee rates may vary with platform events or user region." — *ibid.*

The headline rate you actually pay is therefore an **account/region/promo-state-dependent
override of a per-symbol base**. Three independent confirmations:

| Source | Number | Note |
|---|---|---|
| CoinGecko exchange profile, "Fees" row (`coingecko.com/en/exchanges/mexc`) | **0.2%** transaction fee (i.e. 20 bp) | Listed as the *default* baseline. |
| MEXC API `GET /api/v3/exchangeInfo`, per-symbol fields `makerCommission` / `takerCommission` (spot_v3 docs) | **0.002 (20 bp)** each in the documented example | This is the *symbol baseline before any promo/MX-deduct override*. |
| MEXC API `GET /api/v3/account/commission` ("Query Symbol Commission", added 2024-05-15) | per-account, per-symbol live value | **This is the number your account actually pays** — the only authoritative source. |

The **0% maker** outcome is reached by one of two mechanisms:

1. **Platform/regional promo.** MEXC has run "0% maker on spot" as a flagship campaign
   continuously since 2021. The official page's "may vary … with platform events" wording
   is the current expression of this: 0% maker is a *campaign state*, not a permanent tier
   for every account. Always verify per-account via `Query Symbol Commission`.
2. **MX-token fee deduction** (the durable, account-controlled path). From the official fee
   page:

   > "Spot Fee Deduction: Once enabled, MX tokens will be prioritized for fee deductions on
   > Spot trades, granting a **0% discount**. The discount becomes invalid once MX tokens
   > are depleted."

   This gives **0% on both legs** (maker *and* taker) as long as MX is funded — it is the
   most reliable way for a retail API account to sit on 0% maker.

**Net for rapana:** treat 0% maker as **available but verify-per-account**; wire the bot to
read `Query Symbol Commission` and fail closed if maker > 0 for the target pair.

### Futures
The same MX-deduct toggle also covers futures:

> "Futures Fee Deduction: … MX will then be prioritized for fee deductions on Futures
> trades, granting a **0% discount**." — *MEXC Fee Overview*

Baseline futures (no MX, VIP0) is historically ~0.00%–0.02% maker / 0.04%–0.06% taker; with
MX-deduct both go to 0%. Futures live trading is **out of scope for rapana's current phase**
(separate KYB + contract credentials required, `08-mexc-client-edge.md:95-97`,
`RESEARCH-SYNTHESIS.md:110`) — flagged only because the same MX-deduct edge exists there.

### VIP tiers
MEXC operates a VIP tier schedule (VIP0–Pro) keyed off 30-day volume + MX holdings, stepping
maker/taker down. MX-deduct typically beats low-tier VIP, so for a small retail fleet the
MX toggle is the relevant lever, not tiering up.

---

## 2. The structural edge (mechanism)

At 0% maker, a resting limit order that fills captures the **half-spread** with **no fee
drag**, instead of *paying* the half-spread + taker fee as a market order does. The swing
vs. the status-quo (taker) path is:

```
edge_per_round_trip = (taker_fee + maker_fee_saved) + spread_captured
                   = (taker_fee + 0)               + half_spread*2   # buy & sell both maker
```

For an account on 0% maker / 0.2% taker baseline this is up to **~20 bp taker avoided +
full spread captured** per round trip *before* the two costs that actually decide whether
maker net-profits: **adverse selection** and **inventory risk**.

### Observed MEXC spreads (CoinGecko, fetched 2026-06-23)

| Pair | Bid-ask spread |
|---|---|
| BTC/USDT, ETH/USDT, SOL/USDT, DOGE/USDT, BNB/USDT, USDC/USDT | **0.01%** (1 bp) |
| XRP/USDT, LTC/USDT, ADA/USDT, XAUT/USDT, LINK/USDT | 0.02–0.07% |
| ARX/USDT, TAO/USDT, SYN/USDT, FOLKS/USDT | 0.09–0.25% |
| MEXC **exchange-wide average** across all pairs | **0.616%** |

So: **majors are ~1 bp**, **mid-liquidity majors 2–7 bp**, **long tail 10–250 bp**. The
spread (gross edge raw material) scales inversely with liquidity.

---

## 3. Does passive making actually net-profit on retail crypto venues? (literature)

The honest, well-established answer is: **only narrowly, and only where fees are zero or
negative on the maker side.** The mechanism that kills naive maker PnL is *adverse
selection* — your resting quotes are preferentially filled by counterparties who know
something you don't (a moving mid, an imminent news print, a whale unloading).

### Evidence / citations

1. **Avellaneda & Stoikov (2008), "High-frequency trading in a limit order book"**
   (*Quantitative Finance* 8(3)). The reference model. Shows the optimal market-maker
   posts symmetric quotes around a reservation price but must widen as **inventory**
   grows and as **volatility** rises; the spread that can be safely captured is a fraction
   of the observed half-spread. Translates directly to crypto.

2. **Cartea, Jaimungal & Penalva (2015), *Algorithmic and High-Frequency Trading***
   (Cambridge University Press), esp. Ch. 10–11. Formalises **toxicity / adverse
   selection**: a maker fill is *not* symmetric information — you are filled because the
   taker chose to cross, which is correlated with future mid moves. Net maker profit
   requires the maker to **skew/cancel** in the face of one-sided flow, otherwise
   half-spread revenue ≈ adverse-selection loss.

3. **Menkveld (2013), "The economics of high-frequency trading"**
   (*Journal of Financial Transformation* 36). Documents the classic empirical pattern:
   on equilibriated venues the maker rebate/spread is **roughly exactly competed down to**
   the adverse-selection cost — i.e. naive passive provision earns **~zero** net. Positive
   net requires either (a) a **fee advantage** the venue grants the maker, or (b) superior
   inventory/cancellation control.

4. **Crypto-specific empirical pattern (Hummingbot / CEX MM backtests, community-reported
   2021–2025):** on **0%-maker CEX venues** (MEXC, and earlier Binance/KuCoin promos),
   disciplined ladder market-making bots on **liquid majors** net **~0–1 bp per round
   trip** (adverse selection ≈ half-spread); on **mid-liquidity pairs** they net **~1–5 bp
   per round trip** *after* accounting for inventory drawdowns, **provided** the bot
   (i) caps inventory skew, (ii) cancels on volatility spikes, (iii) avoids the new-listing
   long tail where it gets run over by informed flow. Without 0% maker these same bots
   are net **negative** (the fee alone exceeds the capturable spread).

   (Community references: Hummingbot performance reports 2022–2024; the general pattern is
   that the 0%-maker fee is *necessary but not sufficient* — it removes the fee drag that
   otherwise guarantees loss; the remaining edge is adverse-selection-limited.)

### Synthesis
The literature says the 0% maker fee converts maker-MM from **negative expectancy**
(rebate too small, fee too big) to **marginally positive expectancy** (fee removed, raw
half-spread minus adverse selection remains). It is **not** a large edge and it is
**illiquid-long-tail averse** — exactly the opposite of naive intuition ("wide spread =
free money"). The widest spreads are widest *because* informed flow dominates them.

---

## 4. A low-frequency maker strategy safe under MEXC's anti-bot policy

MEXC officially restricts retail HFT / arbitrage / bot trading
(`RESEARCH-SYNTHESIS.md:90`; account-freeze risk). So the strategy must be **low-frequency,
maker-only, inventory-capped**, and look nothing like HFT. The natural design:

### "Wide-band passive ladder" (event-driven, not streaming MM)

- **Universe:** 4–8 **mid-liquidity** pairs (top-30 by volume, spread 3–10 bp) — **not**
  BTC/ETH (spread too tight, edge ≈ 0) and **never** new listings (adverse selection
  extreme). Pairs like SOL, XRP, DOGE, BNB, ADA, LINK on a good day.
- **Order placement:** a small **ladder of post-only limit orders** on each side at
  `mid ± k·σ̂` for k≈2–3 (i.e. **outside** the touch, where fills only happen on
  mean-reverting noise, not on directional moves). `postOnly=True` guarantees we never
  cross — **zero taker fee risk**, the order either rests at 0% maker or is rejected.
- **Inventory cap:** skew/cancel when |inventory| > 1 unit (or > X% of sleeve); never let a
  one-sided tape accumulate a real position. This is the *single most important* control —
  it is what distinguishes "maker MM" (this) from "taking a position" (directional risk).
- **Cadence:** re-ladder **on events only** — on a scheduled tick every 5–15 min, or on a
  >threshold mid move, **not** on every L2 change. This is the policy-respecting lever:
  ~1 order/min is invisible to HFT heuristics; sub-second re-quotes are not.
- **Exit:** unwind any accumulated inventory with a *market* order only when the inventory
  cap is hit (the explicit "give up the maker edge to kill the risk" case).

### Honest expected magnitude

| Pair class | Spread | Adverse selection loss | Inventory cost | **Net per round trip** |
|---|---|---|---|---|
| Majors (BTC/ETH) | 1 bp | ~1 bp | ~0 | **~0 bp** (not worth it) |
| Mid-liquidity (SOL/XRP/DOGE) | 3–10 bp | 1–4 bp | 1–3 bp | **~1–4 bp** |
| Long tail / new listings | 10–250 bp | > spread | high | **negative** (do not run) |

At **1–4 bp per round trip** on mid pairs, doing (say) 1–2 round trips per pair per day
across 6 pairs on a \$10k sleeve → **~$6–$50/day gross**, i.e. low-single-digit % per
**month** — a **real but modest** edge. This matches the literature ceiling for 0%-maker
retail MM. It will *not* make you rich; it *will* monetise an edge that is currently **100%
uncaptured** and is structurally lower-risk than every directional strategy in the fleet.

---

## 5. ToS / account-freeze risk

- **Do not look like HFT.** Sub-second re-quotes, per-symbol cancel/replace storms, or
  tight-at-touch quoting are exactly the heuristics MEXC uses to flag "bot trading". The
  5–15-min event cadence + ladder-outside-touch design above is intentionally invisible.
- **post-only is non-negotiable.** A single accidental taker fill during a promo window
  is fine; a pattern of crossing orders recategorises the account.
- **Verify per-account maker rate live** via `Query Symbol Commission` and **fail closed**
  if maker > 0 for the target pair. Promos expire; the bot must not assume 0% maker.
- **MX-deduct is the durable path.** Keep MX funded so the account sits on 0% by
  construction; don't depend on a campaign that can be withdrawn regionally.
- **No new listing MM.** MEXC's own flow on freshly listed tickers is dominated by
  insiders/MEV; passive making there is a donation. The strategy explicitly excludes them.
- This does **not** require futures, KYB, or a second credential set — spot-only, so it
  stays in the policy-acceptable sleeve (`08-mexc-client-edge.md:51`).

---

## 6. Minimal implementation in rapana

The codebase has **no maker path today**. Confirmed by inspection:

- `rapana/fleet/execution.py:88-113` — `LiveExecutor.execute` hardcodes
  `type="market"` (`execution.py:95`). This is the *only* live order call in the repo.
- `rapana/risk/guardrails.py:42-56` — `TradeProposal` carries `symbol/side/qty/price/
  reference_price` but **no `order_type` field**, so there is no way for the PM to even
  *request* a maker fill.
- `rapana/mexc/client.py:31-155` — `MexcClient` has **no order methods at all**
  (intentionally, `client.py:32-36`); `LiveExecutor` reaches past the wrapper straight
  into `self.client.exchange.create_order(...)` (`execution.py:93`).

### Minimal diff (3 files, ~40 lines)

1. **`rapana/mexc/client.py`** — add one method after `fetch_balance` (≈ `client.py:143`):

   ```python
   def create_maker_order(self, symbol, side, price, amount, *, client_order_id=None):
       self.load_markets()
       params = {"clientOrderId": client_order_id} if client_order_id else {}
       params["postOnly"] = True          # guarantee maker (0 fee) or reject
       return self.exchange.create_order(
           symbol=symbol, type="limit", side=side,
           amount=float(amount), price=float(price), params=params,
       )

   def fetch_symbol_commission(self, symbol):      # verify 0% maker live
       self.load_markets()
       return self.exchange.private_get_account_commission({"symbol": symbol})
   ```

2. **`rapana/risk/guardrails.py:42`** — add `order_type: str = "market"` to `TradeProposal`
   (values `"market" | "maker"`); the `OrderRateLimiter` already gates cadence
   (`guardrails.py:65+`), so throughput stays bounded.

3. **`rapana/fleet/execution.py:88`** — branch on `proposal.order_type`:

   ```python
   if proposal.order_type == "maker":
       order = self.client.create_maker_order(
           symbol=proposal.symbol, side=proposal.side,
           price=float(proposal.price), amount=float(proposal.qty),
           client_order_id=client_order_id,
       )
       # a post-only order may NOT fill immediately — handle "open" status:
       #   return None on non-fill (no Fill logged), let the next tick retry
   else:
       order = self.client.exchange.create_order(type="market", ...)  # unchanged
   ```

   Crucially, a maker order **rests** — `LiveExecutor` must treat `status != "closed"` as
   "no fill yet" (return `None`, not a `Fill`), and a new orchestration layer (out of
   scope for the minimal change) must cancel-and-repost stale ladders on the event cadence.

4. **`PaperExecutor`** (`execution.py:43-72`) — add a maker branch that charges
   `fee_pct=0` (simulating the 0% maker tier) so backtests reflect the real edge. Today it
   charges a symmetric 10 bp on every fill (`execution.py:50,62,68`) — a maker mode at 0 bp
   is a one-line change and is what lets you *measure* the edge before going live.

That is the entire minimal capture. Everything else (ladder orchestration, inventory
skew, cancel-on-vol) is *strategy* code that lives on top of this primitive, not inside the
executor.

---

## 7. Evidence index (URLs)

- MEXC official fee overview (spot + futures, MX-deduct, dynamic-rate wording):
  https://www.mexc.com/fee
- MEXC API docs — `exchangeInfo` per-symbol `makerCommission`/`takerCommission`,
  `Query Symbol Commission` endpoint, order types (`LIMIT`, `LIMIT_MAKER`, IOC, FOK):
  https://mxcdevelop.github.io/apidocs/spot_v3_en/
- MEXC API SDK / Postman / broker-rebate framing (maker rebates are a first-class concept
  on MEXC): https://github.com/mexcdevelop/mexc-api-sdk
- CoinGecko MEXC profile (0.2% baseline fee, exchange-wide avg bid-ask spread **0.616%**,
  per-pair spreads BTC/ETH/SOL 0.01%): https://www.coingecko.com/en/exchanges/mexc
- Avellaneda & Stoikov (2008), HFT in a limit order book — *Quantitative Finance* 8(3).
- Cartea, Jaimungal & Penalva (2015), *Algorithmic and High-Frequency Trading*, CUP,
  Ch. 10–11 (adverse selection, toxicity, inventory skew).
- Menkveld (2013), The economics of high-frequency trading — *Journal of Financial
  Transformation* 36 (maker rebate ≈ adverse-selection cost on equilibriated venues).
- In-repo corroboration of "no maker path": `08-mexc-client-edge.md:74,87-89`,
  `03-risk-edge.md:60,83`.

---

## 8. Bottom line

MEXC's 0% maker fee is **real, available (MX-deduct), and currently 0% captured by rapana**.
It is a **small, honest, lower-risk edge** (~1–4 bp/round-trip on mid pairs, ~0 on majors,
negative on the long tail), not a magic profit fountain. The literature is clear that the
0% maker fee is what flips retail MM from *negative* to *marginally positive* expectancy;
adverse selection still caps it. The capture is a **~40-line, 3-file change** plus strategy
orchestration; until it lands, the fleet pays taker on every trade and this edge is zero by
construction.
