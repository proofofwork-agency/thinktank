# 15 — MEXC Listing & New-Market Detection (Informational First-Mover)

**Agent:** 15/60 — Listing-detection research
**Scope:** channels for MEXC new-listing / new-market announcements; CCXT `load_markets(reload=True)` polling latency; the realistic *non-HFT* edge; a `ListingWatch` feed design and its plug-in to the Scout universe selector.
**Thesis:** On MEXC there is **no first-seconds snipe edge for a retail API bot** — new listings land in the Innovation/Assessment Zone where API order placement is restricted, and the listing time is pre-announced hours-to-days ahead, so the pop is already arbitraged by the time an API order could cross. The real edge is **informational and selectional**: (1) detect listings early to build a `first_bar_age`/listing-state signal that the current momentum-Scout is structurally blind to (cross-ref agent 06 §b), (2) feed newly-tradeable symbols into the universe as a *confirmation* trigger, and (3) catch delistings — the catastrophic-avoidance twin edge. Detection is a low-frequency event feed, not a latency game.

---

## (a) Actual MEXC announcement channels — verified June 2026

I probed each channel live. The picture is **different from what prior agents recorded**: there is **no official announcement REST API and no RSS**. Everything is web-HTML or social.

### What exists

| Channel | URL | Programmatic access | Verdict |
|---|---|---|---|
| **Announcement Center (canonical)** | `https://www.mexc.com/announcements` | HTML only — **Akamai bot-gated** | Authoritative, but scraping needs a real browser (see §b) |
| New Listings category | `https://www.mexc.com/announcements/new-listings` | HTML, gated | Same as above |
| Delistings category | `https://www.mexc.com/announcements/delistings` | HTML, gated | Same — this is the twin feed (agent 06 edge #3) |
| API Updates category | `https://www.mexc.com/announcements/api-updates` | HTML, gated | Fee/zone changes live here (see §e) |
| Article-by-ID (stable) | `https://www.mexc.com/announcements/article/{id}` (e.g. `17827791536289`) | HTML, gated | Numeric ID alone resolves; slug optional |
| **Telegram (official)** | `https://t.me/MEXC_OfficialAnnouncements` | Public channel; **MTProto read-only (Telethon/Pyrogram)** | **Best free, low-latency signal** — see §b |
| X / Twitter | `@MEXC_Official` / `@MEXC_Global` | API now paid/gated | Lower signal-to-noise, ToS-fragile |
| API support (TG) | `https://t.me/MEXCAPIsupport` | n/a | Reference only |

### What does NOT exist (correcting the record)

- **No announcement REST endpoint.** The legacy `/open/api/v2/announcement/list?type=...` returns **404 (openresty)**. The internal `/api/platform/announcement/list` and `/uuc/api/v1/announcement/list` return **Akamai 403 "Access Denied"** even with a full browser UA + `Referer` + cookie jar. MEXC's public trading API (`api.mexc.com/api/v3`, `contract.mexc.com`) is **market-data + trading only** — there is no `announces` route.
- **No RSS/Atom feed.** `/blog/rss`, `/feed`, `/rss` all **403**. The `/support/articles/...` help-URL form (cited by agent 04) **404s** — MEXC migrated the whole help center into `/announcements` and `/announcements/article/{id}`.
- **Agent 04's claim** (`04-data-edge.md:79,89-93`) that "`MEXC REST /api/v3/announces` or RSS" is a free key-less source is **incorrect**. This report supersedes it. The *opportunity* agent 04 flags is real; the *mechanism* is HTML-scrape or Telegram, not a clean REST endpoint.
- Category/tag URL structure (observed from the live HTML): categories `/new-listings`, `/delistings`, `/api-updates`, etc.; **tags** carry numeric IDs — `spot-18`, `futures-19`, `pre-market-29`, `kickstarter-33`, `meme-31`, `launchpool-28`, `dex-20`. The New-Listings page is itself tag-filterable, which is the parsing seam.

### The listing lifecycle (observed, e.g. ZYLO Jun 23 2026)

A listing is **not** a single instantaneous event. It is a multi-stage **information cascade**, and every stage is published before the next:

1. **Kickstarter / Launchpad voting event** announced (days ahead).
2. **Voting-result + listing-arrangement** announcement — states the **exact listing UTC time**, the zone (almost always "Innovation Zone"), deposit-open time, withdrawal-open time (typically T+24h). *Observed: published ~11h before the 12:00 UTC open.*
3. **Pre-Market** (OTC) phase may open before spot (e.g. NES Pre-Market start 09:00 UTC, spot later) — gives early price discovery.
4. **Spot trading opens** in the Innovation Zone at the stated time.
5. (Delistings mirror this: a delisting announcement states the closure time; futures/spot pairs removed on schedule.)

**Implication:** the listing timestamp is **knowable hours-to-days in advance**. The first-mover "race" is therefore over information that is already public — the people winning the first tick are co-located / OTC desk / pre-funded, not a polling REST bot. The edge for rapana is downstream of this fact.

---

## (b) Programmatic access — what actually works, ToS-safely

### Tier 1 — Earliest signal: Telegram (MTProto read-only)

The official channel `@MEXC_OfficialAnnouncements` is public and posts every listing/delisting/article within seconds of web publication (the announcement page itself says *"Want early signals on listings? Follow MEXC Announcements on Telegram"*). Reading it:

- **ToS-safest:** a **read-only MTProto user-client** (Telethon/Pyrogram) subscribed to a public channel. This is what essentially every community "MEXC listing bot" does. It is a *read* of a *public* channel — not scraping a gated property, not a paid X API, no key.
- **Not-safe / fragile:** scraping X, or running a Telegram *bot* added to a channel that doesn't permit it.
- **Latency:** seconds-to-a-minute after MEXC publishes. This is the closest a free channel gets.
- **Caveat:** MTProto requires a phone-number session; treat it as a single shared read-only relay, not per-strategy. And MTProto clients that poll aggressively can get temp-banned — a single listener forwarding to an internal queue is the right shape.

### Tier 2 — HTML scrape of the Announcement Center (fallback / backfill)

`webfetch` (headless browser) **succeeds** on `/announcements/new-listings`; **curl 403s** even with a full Chrome UA + Referer + cookies (Akamai bot-manager sensor check). So:

- Requires **Playwright/undetected-chromedriver** (real JS execution). A plain `httpx`/`requests` poller will be blocked.
- Use only as **backfill or fallback** (e.g. reconcile the TG relay against the canonical HTML once per cycle). It is heavier, slower, and more brittle than Tier 1; do not make it the hot path.
- Respect the site: one request per category every several minutes, never concurrent. This is the cadence that keeps a scraper on the right side of "tolerable."

### Tier 3 — Markets-map confirmation via CCXT (authoritative, ToS-safe, cheap)

This is what the repo already supports. `MexcClient.load_markets(reload=True)` (`rapana/mexc/client.py:47-51`) calls `GET https://api.mexc.com/api/v3/exchangeInfo`. Verified in the installed `ccxt==4.5.59`:

- `exchangeInfo` has **weight 10** (`ccxt/mexc.py:191`). MEXC spot v3 IP limit is weight-based per 10s; the repo conservatively assumes 300/10s (`client.py:13`). One `exchangeInfo` per minute = 10 weight/min ≈ 0.6% of the budget. **Polling this endpoint every 30–60s is essentially free and looks nothing like HFT.**
- It is a **first-class, documented, key-less public endpoint** — the ToS-safest possible detection path. This is the detection channel rapana should *bet on*; Tiers 1/2 are accelerators.

### Polling latency vs the official announcement (the honest number)

The symbol enters `exchangeInfo` at (or very slightly before) the moment MEXC opens it for query/trade — i.e. **at listing time**, which is **hours after** the Tier-1 announcement. So:

- `load_markets(reload=True)` on a 60s cadence detects a newly-added symbol within **≤60s of it becoming queryable**, but that is **hours late vs the announcement** and **at/after the open vs the pop**.
- Therefore: **Tier 3 cannot be a first-mover signal** — the market-map appearance lags the news. Tier 3's job is *confirmation + universe inclusion*, not alpha timing. This directly answers the brief's "how late is polling?" question: **late enough that timing-alpha is gone, early enough to be a clean selection/inclusion trigger.**

This also matches agent 08's read (`08-mexc-client-edge.md:63,76,92`): no websocket, REST polling only, and `load_markets(reload=True)` is the detection primitive — "event-triggered (only polled right after ... a new symbol), so it does not look like HFT."

---

## (c) The realistic non-HFT edge (and the edges that are *not* there)

### Edges that are dead for a retail API bot (be explicit so we don't chase them)

1. **Sniping the first tick.** Two structural blockers:
   - **Innovation/Assessment Zone API restrictions.** Newly-listed spot pairs almost always open in the *Innovation Zone* or *Assessment Zone*. Per MEXC's own API-Updates announcements, **API Futures explicitly exclude Innovation Zone pairs**, and spot pairs can be **API-disabled per-pair "at the request of the project team"** (e.g. CRTAI/USDT, CRAT/USDT, MNFT/USDT — see `API Suspension for Selected Spot Trading Pairs`). So a freshly-listed token may be **untradeable via API at all** in its first days. (The repo's risk rails would block it anyway: 5% sanity price band `config.py:62` and $250 max notional `config.py:61` reject listing-day prints.)
   - **The pop is pre-arbitraged** — the listing time is public hours ahead; OTC desks and pre-funded whales take the first prints, not a REST bot.
2. **Fee-arb / maker rebate on new books.** API Futures fees were hiked three times in 2026 (maker 0.01%→0.04%→0.06%, taker 0.05%→0.06%→0.08% by Jun 2026). Any taker-side "be first" play now pays 0.06–0.08% to enter *and* exit on a book that is 5–20% wide. Negative expectancy. (Confirms the brief's "MEXC restricts retail HFT/arb" premise — see §e.)

### Edges that ARE there for a low-frequency bot (ranked)

**Edge 1 — Post-listing-drift avoidance via `first_bar_age` (HIGH, the core pay-off).** Cross-ref **agent 06** (`06-universe-edge.md:96-100`) and agent 10 (post-listing drift, pending). MEXC small-cap listings show **negative drift in the 7–60d window** as airdrop recipients exit and unlock cliffs hit. The current Scout (`ranker.py:77` score = `momentum/volatility`) **systematically over-weights fresh listings** because listing-day prints inflate both 30h-momentum and 24h volume (`scout.py:86-89`) — the exact wrong bucket. Listing detection is the **missing input** that makes the `first_bar_age` filter agent 06 recommends *computable*: you can't bucket "age since listing" if you don't know the listing time. **This is the single highest-value use of a ListingWatch feed** — not to *trade* listings, but to *de-select* them from a momentum universe (or route them to a short-bias strategy).

**Edge 2 — Universe-inclusion confirmation trigger (MEDIUM, free).** Today `Scout.discover_candidates` (`scout.py:56-69`) already walks `load_markets()`, so newly-added symbols enter the candidate pool *eventually* — but only when the daily `rebalance_bars` cycle (`config.py:77`, default 24 = daily) next runs, and only if they pass the 31-bar history floor (`ranker.py:94`). A ListingWatch feed lets you (a) persist `first_bar_ts` so age-bucketing is instant, and (b) **optionally** promote a high-conviction new market into the watch list on the *bar after* it has enough history, rather than waiting up to a day. Low alpha, but it closes the "Scout is blind to brand-new listings as a special state" gap (agent 06 §b).

**Edge 3 — Delisting avoidance (HIGH, catastrophic-prevention).** The *twin* feed. Delistings live on the same channel (`/announcements/delistings`, same TG relay) and the same `load_markets` diff detects the symbol going `active: false` / disappearing. Agent 06 edge #3 (`06-universe-edge.md:102-108`): a symbol within N days of a delisting announcement routinely dumps 20–60% as leveraged longs are force-liquidated, and the momentum Scout would *preferentially select* it. Detection → Scout exclusion is worth multiples of any listing-timing alpha. **ListingWatch should really be `MarketLifecycleWatch` (listings + delistings).**

**Edge 4 — Informational/notify-only first-mover (LOW direct alpha, HIGH optionality).** The pre-announced listing time (Kickstarter result, Pre-Market start) is actionable for a **human-in-the-loop**, not the autonomous fleet: pre-funding deposits, manual Innovation-Zone discretionary entries, or risk-prep (tighten bands ahead of a known volatility event). Ship this as an **operator alert** (`notify_console` / `ntfy_topic`, already wired in `config.py:44-46`), not an automated order. Keeps rapana firmly on the read-only side MEXC tolerates (`08-mexc-client-edge.md:105`).

---

## (d) Proposed `ListingWatch` feed for rapana

A **read-only event ingester** that emits structured signals. It is a *new* component alongside the OHLCV/funding ingesters (`data/ingest.py`), feeding the store and the Scout. No orders, no websocket, no Innovation-Zone sniping.

### Architecture (two-tier, defense-in-depth)

```
                ┌─────────────────────────────────────────────────────┐
  Tier 1 (fast) │  Telegram MTProto relay (Telethon/Pyrogram, RO)     │──┐
   secs–1 min   │  @MEXC_OfficialAnnouncements → parse → event         │  │
                └─────────────────────────────────────────────────────┘  │
                                                                        │  ▼
                ┌─────────────────────────────────────────────────────┐  in-process
  Tier 1b (fb)  │  Headless-browser scrape (Playwright)               │──▶ queue /
   backfill     │  /announcements/new-listings + /delistings          │  ledger
                └─────────────────────────────────────────────────────┘  │
                                                                        │  ▼
                ┌─────────────────────────────────────────────────────┐  ┌────────────┐
  Tier 3 (auth) │  CCXT load_markets(reload=True) diff, every 60s      │─▶│ reconcile  │
   confirms     │  (MexcClient, the repo's own client)                 │  │ + emit     │
                └─────────────────────────────────────────────────────┘  └─────┬──────┘
                                                                                   │
                          structured ListingEvent  ◀──────────────────────────────┘
                          → store.listings table   → Scout first_bar_age filter
                          → operator alert (ntfy)  → (optional) backtest events table
```

Tier 3 is **mandatory and always-on** (it's cheap, ToS-safe, and the source of truth for "is this symbol queryable"). Tier 1 is the **accelerator** that turns "detected at open" into "known hours ahead." Tier 1b only runs to reconcile/backfill if Tier 1 is silent for N hours.

### ToS-safe polling cadence

| Source | Cadence | Rationale |
|---|---|---|
| Telegram MTProto | event-driven (listen) | One read-only listener; not polling at all |
| HTML scrape (Tier 1b) | every **10 min** per category, single request | Stays well under Akamai thresholds; headless only when Tier 1 silent |
| `exchangeInfo` (Tier 3) | every **60s** | weight 10 of ~300/10s; trivially within IP limit; pair with `fetch_tickers` reuse |

Net external footprint: **1 TG listener + 1 REST call/min + occasional scrape.** Indistinguishable from a normal client. No HFT signature.

### Emitted signal (structured)

```jsonc
// ListingEvent — one per detected lifecycle change
{
  "symbol": "ZYLO/USDT",
  "base": "ZYLO", "quote": "USDT",
  "kind": "listing",            // listing | pre_market | delisting | api_disabled
  "zone": "Innovation",         // Innovation | Assessment | Main
  "state": "announced",         // announced | pre_market | open | withdrawable | closing | closed
  "announced_ts": 1782249000,   // when the announcement was published (Tier 1)
  "listing_ts": 1782298000,     // MEXC-stated open UTC time (parsed from article)
  "withdrawal_ts": 1782384400,  // T+24h withdrawal open (if stated)
  "detected_ts": 1782249012,    // when *rapana* first saw it
  "confirmed_in_markets": false,// flips true once load_markets sees the symbol (Tier 3)
  "source": "telegram",         // telegram | scrape | markets_diff
  "url": "https://www.mexc.com/announcements/article/17827791536292"
}
```

Two timestamps matter most: **`listing_ts`** (drives age-bucketing and the alert) and **`confirmed_in_markets`** (drives universe inclusion — never include a symbol in the live Scout until this is `true`, because pre-listing the OHLCV calls 404).

### Storage (closes the survivorship/lookahead gap agents 02 & 06 flagged)

New `listings` table in the store (`data/store.py:19-24` schema; agent 02 `02-backtest-edge.md:120-124` already calls for exactly this): `(symbol PK, kind, zone, announced_ts, listing_ts, withdrawal_ts, delist_ts, source, raw_id)`. This:
- Gives `rank_universe` a `first_bar_age`/`zone` filter (agent 06 edge #2) — **both** for live Scout and, via the PIT firewall, in backtest.
- Enables per-bar universe membership `listing_ts <= ref_ts < delist_ts` (`cross_sectional.py:69`, agent 02 §c3) → **kills survivorship bias** in the cross-sectional backtest, the single biggest honesty win available.

### Plug-in to Scout (the actual integration)

Minimal, additive change — reuses the existing pipeline, no strategy-layer rewrite:

1. **Scout discovers as today** (`scout.py:56-69`) but consults the `listings` table to tag each candidate with `first_bar_age` and `zone`.
2. **New `UniverseParams` fields** (`ranker.py:20-26`): `exclude_zones: set = {"Innovation"}` and `min_first_bar_age_bars: int | None`. Default `min_first_bar_age_bars = 168` (7 days @1h) → fresh listings are *excluded* from the momentum universe until they season, directly capturing Edge 1.
3. **Optional promotion hook:** when a `ListingEvent` with `confirmed_in_markets=true` arrives *and* the symbol is past its seasoning floor, the orchestrator (`fleet/orchestrator.py:153-180` rebalance loop) can fast-path it into the next `select_symbols()` rather than waiting up to 24 bars.
4. **Delisting exclusion:** any symbol with a `delisting` event within `delist_horizon_days` (e.g. 7) is dropped from candidates (Edge 3) — and currently-held positions get flagged to the risk gate.
5. **Operator alert:** `announced_ts`/`listing_ts` of any new event → `notify` layer (`config.py:44-46` ntfy/console). Human decides; fleet stays read-only.

### Build order & sizing

| Step | Surfaces | Est. LOC | Depends on |
|---|---|---|---|
| `listings` store table + migration | `data/store.py` | ~40 | — |
| Tier 3 markets-diff detector (reuse `MexcClient`) | new `rapana/feed/listing_watch.py` | ~80 | client.py (exists) |
| `first_bar_age`/`zone` Scout filter | `universe/ranker.py`, `scout.py` | ~40 | listings table |
| Tier 1 Telegram relay (Telethon RO) | new `rapana/feed/tg_relay.py` | ~120 | phone session (human gate) |
| Delisting exclusion + ntfy alert | `scout.py`, `notify` | ~40 | listings table |
| Headless scrape backfill (Playwright) | new `rapana/feed/ann_scrape.py` | ~150 | Playwright dep |

Ship **top-down**: the Tier-3 detector + store table + Scout filter is the 80%-of-value slice and needs zero new external infra. Add the Telegram relay second (the latency win). Treat the headless scraper as optional backfill.

---

## (e) MEXC policy signals worth flagging (why low-freq is the only posture)

Observed in the live API-Updates announcements (Jun 2026):

- **API Futures fees tripled in 2026** (maker 0.01%→0.06%, taker 0.05%→0.08%, Mar/May/Jun). A taker-side HFT/arb play now pays 0.06–0.08% per side and is explicitly carved out of Innovation Zone pairs. This is a deliberate de-marketing of retail API HFT.
- **Innovation/Assessment Zone pairs are API-restrictable**, and individual spot pairs can be API-disabled at project teams' request. *Any* strategy that assumes it can always trade a freshly-listed symbol via API is fragile by construction.
- **API Futures moved domain** `contract.mexc.com` → `api.mexc.com` (Jan 2026) and KYC is now required for Futures API keys; Spot API keys do not need KYC. rapana's read-only posture (`MexcClient` is read-mostly, `client.py:32`) is exactly what this regime rewards.

Net: the regime is pushing API users toward **read-only data + low-frequency, fee-aware execution on seasoned pairs**. Listing detection as a *selection/inclusion/avoidance* signal fits that regime; listing *sniping* does not.

---

## (f) Summary / answers to the brief

- **Channels:** canonical Announcement Center (HTML, Akamai-gated) + official Telegram `@MEXC_OfficialAnnouncements` (best free signal, MTProto RO) + CCXT `load_markets` (authoritative confirmation). **No REST/RSS announcement API exists** — prior agent 04's `/api/v3/announces`/RSS claim is wrong; this report supersedes it.
- **Polling latency:** `exchangeInfo` (weight 10, ~free) detects a new symbol within ≤60s of it becoming queryable — but that is **hours after the announcement and at/after the open**, so markets-map polling is a *confirmation/universe-inclusion* trigger, not a first-mover signal. Tier-1 Telegram is the only sub-minute first-mover channel.
- **Realistic edge:** **NOT** sniping the pop (Innovation-Zone API blocks + risk rails + pre-arbitraged open kill it). **YES** — post-listing-drift *avoidance* via `first_bar_age` (agent 06/10), delisting *avoidance* (agent 06 #3), and clean *universe inclusion*. Plus an operator-only pre-listing alert.
- **Universe trigger:** yes — `confirmed_in_markets=true` is the safe inclusion event; `listing_ts` powers age-bucketing that the current Scout lacks.
- **ListingWatch design:** two-tier read-only feed (TG relay + `load_markets` diff, optional headless backfill), emits the structured `ListingEvent` above, writes a `listings` table that also fixes survivorship bias in the backtest, and plugs into Scout via two new `UniverseParams` filters (`exclude_zones`, `min_first_bar_age_bars`). Ship Tier-3 + table + filter first (~160 LOC, no new infra).

## Cited files
- `rapana/mexc/client.py:13,32,47-51,53,62-69` (rate-limit assumption, read-mostly client, `load_markets`/`symbol_exists`, `fetch_tickers`)
- `rapana/universe/scout.py:56-69,86-89` (candidate discovery, volume prefilter that over-weights fresh listings)
- `rapana/universe/ranker.py:20-26,77,94` (`UniverseParams`, score, 31-bar history floor)
- `rapana/config.py:44-46,61-62,77` (notify, $250 notional, 5% band, rebalance_bars=24)
- `rapana/fleet/orchestrator.py:153-180` (rebalance loop, promotion hook site)
- `rapana/backtest/cross_sectional.py:69` (per-bar universe membership — survivorship fix site)
- `rapana/data/store.py:19-24` (schema — new `listings` table site)
- `.venv/.../ccxt/mexc.py:159-202` (spot v3 base, `exchangeInfo` weight 10)
- Cross-ref: `research/agents/02-backtest-edge.md:42,91,120-124` (listings table + per-bar membership),
  `04-data-edge.md:79,89-93` (claim this report corrects), `06-universe-edge.md:51,77-79,96-108,147` (listing-lookahead, post-listing drift, delisting edge, `first_bar_age`),
  `08-mexc-client-edge.md:63,76,92,105` (detection via `load_markets`, no WS, read-only posture)
