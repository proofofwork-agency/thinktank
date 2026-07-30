# 08 — MEXC client edge inventory

**Agent:** 8/60 · **Scope:** `rapana/mexc/client.py`, `rapana/mexc/__init__.py`, `rapana/config.py`, `rapana/secrets.py`
**Goal:** Enumerate what venue-specific edges are reachable *right now* from this codebase, and what is gated behind new code / new auth.

All citations are `file:line`. CCXT unified-API names are used for the proposed additions.

---

## (a) Method inventory

### `MexcClient` — spot, REST, authenticated-by-default (`rapana/mexc/client.py:31-155`)
Defaults: `defaultType=spot`, `enableRateLimit=True`, `rateLimit=200ms` (`client.py:15-19`).

| Method | Line | CCXT call | Group | Safety |
|---|---|---|---|---|
| `__init__(settings, *, authenticated=True)` | `client.py:38` | `ccxt.mexc(params)` | ctor | n/a |
| `load_markets(*, reload=False)` | `client.py:47` | `exchange.load_markets()` | market metadata | **read-only** |
| `symbol_exists(symbol)` | `client.py:53` | (uses `exchange.markets`) | market metadata | **read-only** |
| `fetch_ticker(symbol)` | `client.py:58` | `exchange.fetch_ticker` | market data | **read-only** |
| `fetch_tickers(symbols=None)` | `client.py:62` | `exchange.fetch_tickers` | market data (bulk 24h screen) | **read-only** |
| `fetch_ohlcv(symbol, timeframe="1h", limit=500, since=None)` | `client.py:71` | `exchange.fetch_ohlcv` | market data | **read-only** |
| `fetch_ohlcv_history(symbol, timeframe, since, until, limit, max_pages)` | `client.py:82` | `exchange.fetch_ohlcv` (paginated) | market data | **read-only** |
| `fetch_order_book(symbol, limit=100)` | `client.py:136` | `exchange.fetch_order_book` | market data | **read-only** |
| `fetch_balance()` | `client.py:141` | `exchange.fetch_balance` | **account** (needs key) | **read-only (private)** |
| `ping()` | `client.py:145` | `exchange.fetch_status` | health | **read-only** |
| `fetch_server_time()` | `client.py:154` | `exchange.fetch_time` | health | **read-only** |

Helper (module-level): `to_perp_symbol(spot)` → maps `BTC/USDT` to `BTC/USDT:USDT` (`client.py:158-168`).

**Order placement: NONE on this class.** The docstring is explicit — *"Order placement is intentionally absent"* (`client.py:32-36`).

### `MexcFuturesClient` — perpetual swaps, REST, **unauthenticated-by-default** (`rapana/mexc/client.py:171-256`)
Defaults: `defaultType=swap`, `rateLimit=200ms` (`client.py:24-28`). Docstring: *"Funding history is PUBLIC ... defaults to unauthenticated ... Order placement ... lands in C4"* (`client.py:172-179`).

| Method | Line | CCXT call | Group | Safety |
|---|---|---|---|---|
| `__init__(settings, *, authenticated=False)` | `client.py:181` | `ccxt.mexc(params)` | ctor | n/a |
| `load_markets(*, reload=False)` | `client.py:189` | `exchange.load_markets()` | market metadata | **read-only** |
| `fetch_funding_rate_history(symbol, since, until, limit, max_pages, now_ms)` | `client.py:195` | `exchange.fetch_funding_rate_history` (paginated, point-in-time via `now_ms`) | market data (carry) | **read-only** |

### Trading (live order placement) — NOT in the client wrapper
The only order code in the repo lives in the **executor layer**, not on `MexcClient`:

- `LiveExecutor.execute` (`rapana/fleet/execution.py:88-113`) calls `self.client.exchange.create_order(type="market", ...)` **directly on the underlying ccxt object**, bypassing the wrapper. Only `RAPANA_ENV=live` (`execution.py:75-83`). Market orders only, with `clientOrderId` for idempotency (`execution.py:92-99`). Paper path simulates a 10 bps fee + 5 bps slip (`execution.py:48-72`).

### Websocket / streaming — **none**
No `watch_*`, no `ccxt.pro`, no socket code anywhere in `rapana/`. All data is REST polling. (A `websockets` lib exists in `uv.lock:1932` but is not imported by the client.)

### Auth wiring
- `rapana/mexc/__init__.py:6-21` `get_keys()` reads `MEXC_API_KEY` / `MEXC_API_SECRET` from the secrets provider and raises if missing. **One credential set, shared** by both `MexcClient` (spot, when `authenticated=True`) and `MexcFuturesClient` (when its `authenticated=True` is passed — never the default).
- `.env.example:16-19` exposes only `MEXC_API_KEY`, `MEXC_API_SECRET`, `MEXC_API_BIND_IP`. **No second key pair for Contract/Futures.**
- `rapana/secrets.py:9-82` is a pluggable `SecretsProvider` (env / static / vault-upgradeable) but stores no venue/type metadata — it cannot today hand back distinct spot vs contract creds.

---

## (b) Reachable venue edges (today, no new client code)

| MEXC edge | Reachable? | How |
|---|---|---|
| **24h ticker stats** (quote-volume screen for universe selection) | **YES** | `MexcClient.fetch_tickers` (`client.py:62`); consumed by `universe/scout.py:16,43` |
| **Order-book depth** (L2 snapshot) | **YES** | `MexcClient.fetch_order_book` (`client.py:136`) |
| **New-listing detection** (symbols appearing in the market map) | **YES** | `MexcClient.load_markets(reload=True)` + `symbol_exists` (`client.py:47,53`); `cli.py:836,843` already runs ingest loops |
| **OHLCV history** (deep, paginated) | **YES** | `fetch_ohlcv_history` (`client.py:82-134`) with stuck-page guard |
| **Funding-rate history** (carry backtest / C1) | **YES, public, no KYB** | `MexcFuturesClient.fetch_funding_rate_history` (`client.py:195`), unauthenticated by default; point-in-time filtered via `now_ms` |
| **Account balance** (equity / sleeve cash) | **YES** (private read) | `fetch_balance` (`client.py:141`) |

These six are the reachable edge surface. All are **read-only / event-style**, which is the only posture MEXC's anti-bot policy tolerates for retail (see `RESEARCH-SYNTHESIS.md:90,108`).

---

## (c) Gaps — not reachable without new code or a second auth scheme

1. **The 0% spot maker fee / maker-rebate edge is NOT captured.** There is no limit/maker order path anywhere — `LiveExecutor` only sends `type="market"` (`execution.py:95`). To actually bank MEXC's headline zero-maker edge you need `postOnly` limit orders, which would be a **new client method** (see d-1).
2. **Recent trades / tape microstructure** — no `fetch_trades` wrapper, so the new-listing-momentum tape (first prints after a listing) is invisible. Only top-of-book + OHLCV are reachable.
3. **No websocket streaming.** Event-driven latency edges (instant new-listing fire, real-time book imbalance, funding settlement tick) all require polling today; this caps the achievable latency and risks tripping MEXC's HFT/arb heuristics if polled too aggressively (research warning, `RESEARCH-SYNTHESIS.md:108`).
4. **Single shared credential scheme for spot & contract.** `get_keys()` returns the same `apiKey/secret` for both `MexcClient` and `MexcFuturesClient` (`__init__.py:6-21`; both callers `client.py:42,185`). The research explicitly warns **not to reuse one client/credential set across Spot and Contract** — futures live trading needs KYB and a separate Contract key set (reopened 2026-03-31, `RESEARCH-SYNTHESIS.md:110`). `secrets.py` has no slot for distinct contract credentials.
5. **No private trade / order history** — `fetch_my_trades`, `fetch_open_orders`, `fetch_closed_orders`, `cancel_order` are all absent, so post-trade reconciliation and cleanup of stuck orders must be done by hand or out-of-band today.
6. **No withdraw/deposit surface** — intentionally and correctly absent (`execution.py:79` "withdraw API is never touched"); flagged only for completeness.

---

## (d) Proposed client additions (2-3, policy-respecting)

Each is **low-frequency / maker / event-driven** to stay inside MEXC's retail anti-bot envelope. CCXT unified method in parens.

1. **`create_maker_order(symbol, side, price, amount, *, client_order_id)` on `MexcClient`** → `exchange.create_order(type="limit", postOnly=True)`.
   **Unlocks:** the actual 0% spot maker fee / rebate edge — the single highest-value MEXC venue feature, currently 100% unreachable. `postOnly` guarantees the order either rests (maker, 0 fee) or is rejected, never crosses into taker territory. Pair with the existing `clientOrderId` idempotency pattern in `LiveExecutor` (`execution.py:92`). Low-frequency by construction (rests on book).
   *File:* add to `rapana/mexc/client.py` after `fetch_balance` (≈ `client.py:143`); rewire `LiveExecutor` to prefer it.

2. **`fetch_recent_trades(symbol, limit=100)` on `MexcClient`** → `exchange.fetch_trades`.
   **Unlocks:** new-listing tape / first-print momentum — the research's "event" category — without websocket infra. Cheap (single REST call), event-triggered (only polled right after `load_markets(reload=True)` detects a new symbol), so it does not look like HFT. Complements the existing new-listing detection in (b).
   *File:* add to `rapana/mexc/client.py` after `fetch_order_book` (≈ `client.py:138`).

3. **Split auth scheme: `get_keys(scope="spot"|"contract")` in `rapana/mexc/__init__.py` + slots in `secrets.py`.**
   **Unlocks:** safe, research-compliant separation of the Spot sleeve from any future Contract sleeve (KYB-gated). This is a precondition, not an alpha edge itself, but it de-risks the C4 futures-live phase and respects the research's "don't reuse one client" rule (`RESEARCH-SYNTHESIS.md:110`). Keeps `MexcFuturesClient` read-default and lets it opt into contract-specific credentials only when human-approved.
   *Files:* `rapana/mexc/__init__.py:6` (extend signature), `rapana/secrets.py` (add `MEXC_CONTRACT_API_KEY`/`_SECRET`), `.env.example:16-19` (document the new pair).

*Optional 4th (deferred):* a `ccxt.pro.mexc` async watcher (`watch_order_book`, `watch_ticker`) for true event-driven new-listing fires. Higher infra cost (async runtime, reconnect logic), so ranked below 1-3.

---

## Bottom line

The 0% spot maker fee is MEXC's marquee edge but is **not** reachable today (market-only executor). The reachable edges are all read-only and event-style — **funding-rate history (carry, no KYB), full-market 24h ticker screen, L2 depth, and new-listing detection via `load_markets(reload=True)`** — exactly the posture MEXC's anti-bot policy tolerates.
