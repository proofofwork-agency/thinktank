# Research 04 — Data Ingest vs. Non-Standard Edge Gap

**Scope:** `rapana/data/` (store.py, ingest.py), `rapana/feeds/`, `rapana/mexc/client.py`, `rapana/fleet/data_provider.py`.
**Thesis:** The fleet can currently ingest OHLCV + settled funding history and consumes two free sentiment feeds. Everything else a non-standard edge would require — order-book microstructure, recent trades, OI, current funding, listing announcements, on-chain flows, unlock calendars, ETF/stablecoin macro — is either wrapped-but-unused, stubbed, or entirely absent. The gap is wide and is exactly where new edge lives.

---

## (a) Current Data Inventory — what the fleet CAN ingest/query

### Storage backend
- SQLite at `RAPANA_DB_PATH` (default `./data/rapana.db`) — `rapana/config.py:34`, `rapana/data/store.py:54-56`.
- Designed as a swap-in point for TimescaleDB/QuestDB later — `rapana/data/store.py:47-52`.

### Tables & schema (`rapana/data/store.py:13-43`)
| Table | Columns | Primary key | Purpose |
|---|---|---|---|
| `candles` | `symbol, timeframe, ts, open, high, low, close, volume` | `(symbol, timeframe, ts)` | OHLCV — `store.py:14-24` |
| `funding` | `symbol (perp), ts, funding_rate` | `(symbol, ts)` | Settled perp funding — `store.py:29-34` |
| `meta` | `key, value` | `key` | Generic KV (ingest cursors, run state) — `store.py:39-42` |

Indices: `idx_candles_symbol_tf_ts` (`store.py:26-27`), `idx_funding_symbol_ts` (`store.py:36-37`).

### Supported OHLCV timeframes
`1m, 5m, 15m, 30m, 1h, 4h, 1d` — `rapana/data/ingest.py:12-13`. Default ingested timeframe is **1h** (`ingest.py:40`).

### Queryable series (public surface)
- `fetch_candles(symbol, tf, limit=500)` — last N bars ascending — `store.py:91-104`.
- `fetch_candles_range(symbol, tf, since, until)` — full history, no limit — `store.py:106-129`.
- `fetch_funding_range(symbol, since, until)` — full funding history — `store.py:172-194`.
- `symbols(timeframe)`, `funding_symbols()` — distinct series — `store.py:131-138`, `196-202`.
- `last_timestamp`, `last_funding_timestamp` — resumable ingest cursors — `store.py:140-148`, `204-211`.

### Universe / symbols
- Default watch list: `BTC/USDT, ETH/USDT, SOL/USDT` — `rapana/config.py:31`, `config.py:104-105`.
- `universe_mode = fixed` by default; `auto` mode screens top-N by 24h quote volume via `fetch_tickers` — `config.py:71-78`, `rapana/universe/scout.py:78`.

### Ingesters (`rapana/data/ingest.py`)
- `MarketDataIngester` — OHLCV; drops the unclosed current bar (`_drop_unclosed`, `ingest.py:16-29`); paginates deep history (`ingest_history`, `ingest.py:71-100`).
- `FundingIngester` — settled perp funding only; point-in-time correct — `ingest.py:124-189`. Uses `MexcFuturesClient` (unauthenticated by default — funding is public).

### Already-wired external feeds (`rapana/feeds/`)
- `FearGreedFeed` — alternative.me F&G, free, no key, 30-min cache, contrarian score in [-1,1] — `rapana/feeds/feargreed.py:13-51`.
- `MarketPremiumFeed` — CoinGecko global avg vs MEXC last; bullish on discount — `rapana/feeds/market_premium.py:12-66`. Coin-id map covers 8 majors (`market_premium.py:14-17`).
- Both feeds emit `(score, confidence)` to analyst agents; **neither writes a time series to the store** — they are real-time signal callables, not historical corpora. There is no `sentiment` or `macro` table.

### Analyst agents that *would* consume external data
- `SentimentAnalyst` — stub: returns neutral unless a `sentiment_fn` is injected — `rapana/agents/sentiment.py:14-31`.
- `MacroAnalyst` — stub: returns neutral unless `macro_fn` injected — `rapana/agents/macro.py:13-31`.
- `Arbitrageur` — stub: returns neutral unless `arb_fn` injected — `rapana/agents/arbitrage.py:13-34`.

> All three are **wired but empty** — they explicitly say "no feed configured" on every cycle. The fleet runs spot-OHLCV-only in practice.

---

## (b) Unused MEXC Client Capabilities

`MexcClient` (`rapana/mexc/client.py:31-155`) and `MexcFuturesClient` (`client.py:171-256`) wrap `ccxt.mexc`. The table below maps every public method to its current production usage.

| Capability | Client method (file:line) | Used in production? | Where it would matter |
|---|---|---|---|
| Markets metadata | `load_markets` `client.py:47` / `189` | YES — Scout, ingest | — |
| Bulk 24h tickers | `fetch_tickers` `client.py:62` | YES — `universe/scout.py:78` | — |
| Single ticker | `fetch_ticker` `client.py:58` | YES — `fleet/data_provider.py:47` | — |
| OHLCV (page) | `fetch_ohlcv` `client.py:71` | YES — `data/ingest.py:49`, `universe/scout.py:97` | — |
| OHLCV (paginated history) | `fetch_ohlcv_history` `client.py:82` | YES — `data/ingest.py:89` | — |
| Funding-rate history (perp) | `MexcFuturesClient.fetch_funding_rate_history` `client.py:195` | YES — `data/ingest.py:162` | — |
| Balance (private) | `fetch_balance` `client.py:141` | YES — `cli.py:55`, `risk/live_safety.py:103` | — |
| Connectivity | `ping` `client.py:145` | YES — `cli.py:51` | — |
| **L2 order book** | **`fetch_order_book` `client.py:136-138`** | **NO — defined but zero production callers** (grep finds only the definition). Tests stub it (`tests/test_mexc_client.py:34`) but nothing consumes it. | Microstructure: imbalance, sweep detection, liquidity-wall stops, spoofing/absorption read |
| **Server time** | **`fetch_server_time` `client.py:154-155`** | **NO — defined, no production caller.** | Clock-skew guard for order signing; timestamp alignment for event studies |

### Capabilities ccxt exposes that the client does NOT wrap at all
| Capability | ccxt primitive | Difficulty | Enables |
|---|---|---|---|
| **Recent trades / tape** | `fetch_trades` / `watch_trades` (ws) | Trivial — same `ccxt.mexc` object, add one method | Tape reading, large-print detection, volume-clock triggers, real-time volatility |
| **Current / next funding** | `fetch_funding_rate` | Trivial — sibling to the already-wrapped history method | Predicted-funding carry, intrainterval funding-spike (vs settled-only today) |
| **Open interest (perp)** | `fetch_open_interest` / `fetch_open_interest_history` | Trivial on `swap` type | Positioning squeeze model (OI + funding combo is the classic), validates the `funding_spike` backtest (`backtest/funding_spike.py:9-12`) |
| **Perp mark OHLCV** | `fetch_ohlcv` on `MexcFuturesClient` | Trivial | Spot-vs-perp basis series (currently basis is only inferred via funding, never priced) |
| **Listing announcements** | NOT in ccxt — MEXC REST `/api/v3/announces` or RSS | Moderate — custom endpoint + parser | New-listing pop, the canonical MEXC "first-to-list" edge (see §c) |

> The `MexcFuturesClient` is essentially a single-method class (`fetch_funding_rate_history`). Everything else perp-related — current funding, OI, mark price, perp OHLCV — is one line of `self.exchange.<primitive>()` away and currently absent.

---

## (c) External Non-Price Feeds a Non-Standard Edge Would Need

Each row: feed → status → source / cost → difficulty → strategy it unlocks.

### c.1 New-listing announcements (RSS / REST)
- **Status:** entirely absent. `MexcClient` does not wrap MEXC's `/api/v3/announces`. No parser, no `announcements` table.
- **Source:** MEXC official announcement RSS/REST (free, no key) — `https://www.mexc.support/help/articles/…` / `mexcdevelop.github.io`. Cross-check: MEXC Twitter @MEXC_Global.
- **Difficulty:** **Low–Moderate.** Free API; work is parsing + dedup + symbol-onboarding latency (sub-second target). No third-party key.
- **Enables:** new-listing momentum / "list-and-pump" capture — MEXC's explicit market position is being first-to-list; first minutes after listing have maximal dislocation. Also front-running the listing by spot-depositing ahead of the open.

### c.2 Perpetual funding + open interest + basis (combined)
- **Status:** funding *history* is wired (`data/ingest.py:124-189`); **current/next funding and OI are not.** Cross-venue basis is computed nowhere (no perp OHLCV stored, no second venue).
- **Source:** all free via ccxt on MEXC; cross-venue basis needs Binance/Bybit added (still ccxt, free).
- **Difficulty:** **Low** (single-venue) / **Moderate** (cross-venue basis — second client + clock sync).
- **Enables:** crowded-positioning unwind (already prototyped in `backtest/funding_spike.py`), squeeze model (funding × OI × price), basis-trade / cash-and-carry, predicted-funding carry.

### c.3 Order book L2 (already wrapped — just unused)
- **Status:** `fetch_order_book` exists at `client.py:136-138` with **zero production callers**. No persistence, no features.
- **Source:** free, MEXC via ccxt (REST poll) or MEXC WS depth stream.
- **Difficulty:** **Very Low** to wire polling (method already exists); **Moderate** for WS + L2 snapshot reconstruction (order-book deltas).
- **Enables:** microstructure strategies impossible from OHLCV — order-flow imbalance, sweep/stop-hunt detection, liquidity-wall stop placement, spoofing/absorption read, real-time slippage model for execution sizing.

### c.4 Recent trades / tape
- **Status:** not wrapped; no `trades` table.
- **Source:** free via ccxt (`fetch_trades`) or MEXC WS `aggTrade`.
- **Difficulty:** **Low** (REST) / **Moderate** (WS volume-clock).
- **Enables:** volume-clock triggers, large-print / block-trade detection, real-time volatility, "smart money" footprint.

### c.5 On-chain whale transfers
- **Status:** absent. `MacroAnalyst` is a stub (`agents/macro.py:27-28`).
- **Source:** Whale Alert (free tier ~10 req/min, paid up), Glassnode (paid, ~$30/mo entry), Arkham (free UI / paid API), Etherscan/Solscan free per-address.
- **Difficulty:** **Moderate.** Free tier is usable for the largest caps; lower-cap coverage needs paid.
- **Enables:** CEX-inflow/outflow signal (whales moving to MEXC = distribution risk), stablecoin mint/burn leading indicator, exchange-balance precursor to price moves.

### c.6 Token unlock / vesting calendars
- **Status:** **placeholder only.** `.env.example:61-62` defines `CRYPTORANK_API_KEY` — but grep finds it is **never imported anywhere in `rapana/`**. No code reads it, no unlock series is stored.
- **Source:** CryptoRank API (key already provisioned in env, unused), TokenUnlocksApp (free), DefiLlama unlocks (free, no key).
- **Difficulty:** **Low.** DefiLlama is free + no key; CryptoRank key is already in the env file.
- **Enables:** unlock-event reversion / inflation-edge (post-unlock supply shock), avoiding concentrated-clone risk ahead of large vests.

### c.7 Stablecoin supply (USDT/USDC market cap, mint/burn)
- **Status:** absent.
- **Source:** DefiLlama (free, no key), CoinGecko (free), Glassnode (paid).
- **Difficulty:** **Very Low.** Free + structured.
- **Enables:** global liquidity regime filter — stablecoin mints historically lead crypto rallies by days; suppresses trading against a tightening-liquidity regime.

### c.8 ETF flows (BTC/ETH spot ETF AUM, net flow)
- **Status:** absent.
- **Source:** SoSoValue (free), CoinShares (free weekly PDF / paid daily API), Farside Investors (free, scrape-able).
- **Difficulty:** **Low.** Free sources, daily cadence only.
- **Enables:** demand-shock regime filter for BTC/ETH — large inflow day → next-day drift; complements the macro analyst.

### c.9 Social sentiment (X/Reddit/Discord, news NLP)
- **Status:** stub only (`agents/sentiment.py:14-31`); only the *aggregate* Fear&Greed index is wired, no per-symbol sentiment.
- **Source:** free = CryptoPanic, LunarCrush free tier, Reddit API (free), RSS news; paid = Santiment, TheTie, LunarCrush Pro.
- **Difficulty:** **Moderate–High.** Per-symbol signal needs NLP/LLM scoring + rate-limit juggling.
- **Enables:** headline-driven fade/momentum, per-symbol fear/greed (vs the global index), rumor-driven listing pops.

### c.10 Google Trends
- **Status:** absent.
- **Source:** Google Trends (unofficial free, `pytrends`), no key, throttled heavily.
- **Difficulty:** **Low** to wire, **High** to keep alive (rate limits).
- **Enables:** retail-attention leading indicator (searches lead retail buying); weak per-symbol but useful as a regime multiplier.

### c.11 Server time / clock skew
- **Status:** `fetch_server_time` exists (`client.py:154-155`), **unused**.
- **Source:** free via ccxt.
- **Difficulty:** **Trivial.**
- **Enables:** not an edge per se — it is a correctness prerequisite for live order signing (recvWindow, expiry) and for aligning event-study timestamps to exchange time.

---

## (d) Feed → Strategy Mapping (compact)

| Missing feed | Strategy class it unlocks | Free? | Effort | Edge type |
|---|---|---|---|---|
| **New-listing announcements** | Listing-momentum capture, pre-listing accumulation | Yes (MEXC RSS) | Low–Mod | Event-driven, latency-sensitive |
| **Current funding + OI** | Squeeze model, predicted-funding carry, basis-trade | Yes (ccxt) | Low | Positioning / carry |
| **Order book L2** (already wrapped!) | Order-flow imbalance, sweep/stops, spoofing read | Yes (REST/WS) | Low (poll) / Mod (WS) | Microstructure |
| **Recent trades / tape** | Volume clock, block-print detection | Yes | Low–Mod | Microstructure |
| **Cross-venue basis** (perp OHLCV on 2nd venue) | Cash-and-carry arb, cross-venue funding arb | Yes | Moderate | Arbitrage |
| **Token unlocks** (CryptoRank key already in env!) | Unlock reversion, vest-inflation fade | Yes (DefiLlama) / paid (CR) | Low | Event-driven |
| **Stablecoin supply** | Liquidity-regime filter | Yes | Very Low | Macro filter |
| **ETF flows** | Demand-shock regime filter (BTC/ETH) | Yes | Low | Macro filter |
| **On-chain whale transfers** | Distribution-risk warning, inflow/outflow leading | Free tier / paid | Moderate | On-chain leading |
| **Social sentiment (per-symbol)** | Headline momentum/fade | Free tier / paid | Moderate–High | Sentiment |
| **Google Trends** | Retail-attention multiplier | Yes | Low (fragile) | Macro multiplier |
| **Server time** | Correctness gate for live orders | Yes | Trivial | Infra (not edge) |

### Sharpest gaps (ranked by EV / effort)
1. **New-listing announcements** — biggest *non-standard* edge, free, MEXC-native, fully absent, project already pivoted to event-driven (`backtest/funding_spike.py:1-5`).
2. **Order book L2 + current funding + OI** — already half-wrapped (`client.py:136`, `client.py:195`), all free, instantly converts the fleet from "OHLCV-only" to "microstructure-aware".
3. **Token unlock calendar** — the `CRYPTORANK_API_KEY` is already in `.env.example:62` and unused; literal dead-config. Cheapest fix, real event edge.
4. **Stablecoin supply / ETF flows** — free, daily, low-noise macro filters that would let the macro agent stop emitting "no feed configured" on every cycle.

---

## Single highest-value missing feed (summary)

**New-listing announcements (MEXC RSS/REST).** The fleet ingests only OHLCV + settled funding; `MexcClient.fetch_order_book` (`rapana/mexc/client.py:136`) and `fetch_server_time` (`client.py:154`) are wrapped-but-unused, and there is no wrapper for trades, current funding, open interest, or listing announces. MEXC's stated market position is "first-to-list," the project has already pivoted to event-driven research (`backtest/funding_spike.py:1-5`), and the new-listing feed is free, key-less, and entirely absent — the canonical non-price edge this fleet is structurally blind to today.
