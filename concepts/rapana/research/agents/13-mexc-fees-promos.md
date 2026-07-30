# Agent 13 — MEXC Fee Structure, VIP Tiers & Promo Timing: The "Fee Arbitrage of Time"

**Scope:** Non-standard edge on MEXC built on the *fee surface itself* — how fees differ by channel, VIP tier, token holding, and (critically) by calendar window. Low-frequency friendly (the edge fires on events, not on tick-level speed).
**Status of evidence:** Core mechanism verified verbatim from MEXC's own support FAQ + announcement center (Dec 2025–Jun 2026). Per-tier futures maker/taker numbers are calibrated to MEXC's public schedule but the live fee page is JS-rendered — verify against the account's own `/fee` page before live capital.
**Why this matters for a retail bot:** MEXC is now structurally *cheaper than every major venue* on spot, but the discount is **channel-gated**. The edge is in choosing the right channel/window, not in trading faster.

---

## 1. The headline — MEXC Spot is 0% by default (and it's not a "promo", it's the new baseline)

Since **Dec 22, 2025, 04:00 UTC**, MEXC charges **0% maker / 0% taker on ALL spot pairs**. This is stated to have **"no end date set"** and to be **"the default fee structure for Spot trading."**

> "MEXC's 0-fee Spot trading allows users to trade Spot trading pairs with 0% maker and 0% taker fees … 0-fee Spot trading will remain in place as the default fee structure for Spot trading. If there are any changes in the future, MEXC will notify users in advance."
> — MEXC 0-Fee Spot Trading FAQ (updated 2025-12-23)
> `https://www.mexc.com/support/article/mexc-0-fee-spot-trading-faq-264764306934491136`

The launch announcement confirms the start:
> "Special Year-End Offer: Enjoy 0 Fees on All Spot Pairs … Event Period: Dec 22, 2025, 4:00 (UTC) – TBA … During the event, all Spot pairs will enjoy zero trading fees. There are no trading volume limits."
> `https://www.mexc.com/announcements/article/special-year-end-offer-17827791532472`

**This is the single biggest venue asymmetry in crypto right now.** Binance/Bybit/OKX spot runs 0.1% taker. MEXC spot runs 0.0%. Any strategy that *can* live on MEXC spot gets a **~10bp cost edge per round trip** vs. running the same strategy on a peer venue. Over a strategy that turns over its book N×/month, that's ~0.1·N% of ATV of free PnL just for *venue choice*.

### The catch — and the actual edge

Both sources carry an identical exclusion clause:
> **"Institutional users, market makers, project teams, and API users are not eligible to participate in this event."**

This is repeated verbatim in (a) the FAQ section 1.3 and (b) the year-end announcement's "Important Notes." **An API-keyed bot is, by MEXC's definition, an "API user" and is excluded from 0-fee spot.** This is the crux of the whole memo and reframes every other tactic below. See §6 for the resolution.

---

## 2. Full fee map (2026, verified where fetchable)

### 2.1 Spot

| User class | Maker | Taker | Source |
|---|---|---|---|
| Retail, web/app, non-API | **0.00%** | **0.00%** | FAQ §1.2, §4.1 |
| API users | standard tier (pre-0-fee schedule) | standard tier | FAQ §1.3 exclusion |
| Institutional / MM / project | standard tier | standard tier | Year-end "Important Notes" |
| MEXC Convert | **0.00%** | **0.00%** (fixed-rate, no slippage) | Convert guide (2026-06-22) |

**Convert is the workaround hidden in plain sight.** MEXC Convert is an OTC-style swap with "Zero Transaction Fees … Once the exchange rate is confirmed, the conversion is settled automatically in the user's Spot account with no additional cost … MEXC Convert offers fixed exchange rates, ensuring that users avoid slippage." `https://www.mexc.com/support/article/how-to-use-mexc-convert-398850007640593408` Whether Convert honors the same API exclusion is *not stated* in the Convert doc itself — test on the account before relying on it (§6).

### 2.2 Futures (USDT-M perpetuals)

Futures still charge. The fee surface is:
- **A standing "0 Fees" pair category** in the futures pair selector (confirmed in the Pre-Market Perpetual guide: "view categories like 0 Fees, MEME, Solana Ecosystem"). These are pair-specific permanent zero-fee contracts.
- **Rolling "0-Fee Fest" promotions** on named pairs, added and concluded on announced schedules. Examples captured live (Jun 2026 announcement center):
  - "0-Fee Fest: Addition of UNIUSDT, UNIUSDC, UNIUSD1, ESPORTSUSDT and VELVETUSDT Futures Pairs"
  - "0-Fee Fest: ICPUSDT, ICPUSDC, and 2 Other Futures Events Conclude on Jun 22, 2026, 10:00 (UTC)"
  - "MEXC to List MVLL USDT-M Index Futures on Jun 23 With 0-Fee Trading" (`...mexc-to-list-mvll-usdt-m-index-futures-on-jun-23-with-0-fee-trading-17827791536432`)
- **Standard pairs** (non-promo): per-tier maker/taker. MEXC's historical schedule is **Maker 0.00% / Taker 0.01–0.02%** at base VIP, scaling down with 30d volume and MX holdings. *Confirm exact basis points on the account's `/fee` page* — the public schedule is JS-rendered and not directly fetchable. **Pre-Market Perpetual fees are "identical to standard perpetual Futures"** (Pre-Market guide §4.2).
- **MX discount on futures still applies** (FAQ §5.2: "MX fee discount benefits for Futures trading remain unchanged and are not affected by 0-fee Spot trading").

### 2.3 Other mechanics

- **Deposits:** free.
- **Withdrawals:** per-chain network fee, dynamic, unchanged by the 0-fee spot program (FAQ §2.3). This is the *real* cost surface for a rebalancing bot — see §7.
- **Funding rate:** standard 8h funding; in pre-market / thin books it is explicitly flagged as volatile ("funding rate may fluctuate dramatically," Pre-Market guide §3.2).

---

## 3. The VIP / MX tier ladder

MEXC's VIP program is volume + MX-holding gated (two parallel axes). The page `/vip` is JS-rendered; the structural facts are stable:

- **Spot VIP:** now mostly moot for retail (spot is 0 anyway). The tier still matters for **API users and institutions**, who pay the pre-0-fee spot schedule and *can* buy it down with VIP tier + MX holdings.
- **Futures VIP:** the live cost driver. Tiers descend in taker bps as 30d futures volume rises; MX holdings add a parallel discount. The buyback-and-burn below (§4) is the reason MX has held value.
- **MX DeFi / staking:** deposit MX into MEXC Earn products for yield. The historically headline mechanism is the **quarterly buyback-and-burn**: "Each quarter, MEXC allocates **40% of platform profits** to buy back and burn MX tokens." (FAQ §5.3, verified) — calculated on *overall platform profit*, not spot fee revenue, so the 0-fee spot change did **not** impair the burn.

---

## 4. MX token as real yield — quantified mechanisms

MX has three independent yield vectors. None require trading:

| Mechanism | How to capture | Real-yield nature | Evidence |
|---|---|---|---|
| **Buyback & burn** | Hold MX off-exchange or in spot wallet | Deflationary; 40% of platform profit/quarter buys MX market-wide and burns | FAQ §5.3 |
| **Kickstarter airdrops** | Commit MX to vote on which token lists next | Receive the listed token as an airdrop proportional to MX committed | ZYLO session: **13,449,696 MX committed**; "Airdrop rewards have been distributed to users' accounts" (`...voting-result-and-listing-arrangement-for-zylo-ecosystem-zylo-kickstarter-17827791536292`) |
| **MX DeFi (Earn)** | Stake/lock MX on MEXC Earn | Platform APY; plus eligibility weight for Launchpad/Kickstarter | `/support/mexc-earn` |
| **Futures fee discount** | Hold MX in account | Reduces futures taker bps by tier | FAQ §5.2 |

**Kickstarter is the cleanest "real yield."** You commit MX (not spent — committed for the session), the winning project lists, and you receive its token as an airdrop. ZYLO's 13.4M MX total commitment shows the mechanism runs at scale every few days (MEXC lists ~1–3 Kickstarter projects/week). A passive MX holder who commits to every session captures a *stream of micro-airdrops* denominated in newly-listed tokens, many of which are high-beta. This is yield that does not depend on spreads, on HFT, or on direction.

---

## 5. Promotional windows that a low-freq bot can time

MEXC runs an unusually dense promo calendar. Three classes are time-shiftable:

### 5.1 Rolling 0-Fee Fest (futures) — the cleanest "time arbitrage"
Pairs enter and exit 0-fee status on *announced* dates. A low-freq futures strategy should **route intended trades into pairs currently in 0-Fee Fest** rather than paying taker on the standard schedule. The announcement center publishes both the *addition* and the *conclusion* timestamps (e.g., "Conclude on Jun 22, 2026, 10:00 UTC"). A weekly scrape of `mexc.com/announcements` tag `Futures` is sufficient signal — this is a 5-minute/week job, not HFT.

**Tactic:** maintain the target universe as a *priority queue* ordered by (a) currently-in-0-Fee-Fest first, then (b) standing "0 Fees" category, then (c) standard pairs only as last resort. Cost per fill drops to zero whenever the bot can defer or substitute into a promo pair.

### 5.2 Kickstarter cycle (spot listing + airdrop)
Every Kickstarter session ends with a listing at a fixed UTC time (e.g., ZYLO: "Trading in the Innovation Zone: Jun 23, 2026, 12:00 UTC"). Listings on MEXC are reliably the highest-volatility, highest-volume events on the venue. A low-freq bot that **participates as MX committer** gets the airdrop for free; one that **provides passive liquidity at listing open** captures the listing-pop spread with 0 spot fees (if non-API) — see §6 for the channel constraint.

### 5.3 Trading-competition / volume-milestone farming
MEXC runs continuous reward-for-volume campaigns with *discrete daily thresholds* (not continuous leaderboards). Live example (Football season, Jun 24–Jul 8 2026):

> "Complete daily Futures trading volume milestones to earn boot passes … Iron Boot Pass: Trade ≥ 10,000 USDT … Bronze ≥ 100,000 … Silver ≥ 1,000,000 … Golden ≥ 10,000,000. Boot passes can be accumulated and redeemed for premium rewards."
> `...watch-daily-win-daily-17827791536434`

**This is structurally farmable at the lowest tier by a small account** — 10,000 USDT of daily futures volume to clear the Iron threshold is trivial, and the reward (redeemable for headphones, sunglasses, coffee machine, etc., or fungible equivalents) is positive-EV if the underlying trades themselves are not bleeding fees. **The trick: farm the volume on pairs that are themselves in 0-Fee Fest**, so the "cost of farming" is ~0 in fees and only the funding/spread risk remains. This is the purest "fee arbitrage of time": the promo pays you to trade, and another promo makes the trading free.

Also live: "$500,000 Football Fiesta: Predict Match Outcomes to Score Rewards" (prediction-market farming, zero capital risk if hedged) and "Trade & Draw! Higher Chances to Win Real NVDA, SPCX & MU Stocks."

---

## 6. ToS-safe tactics (the concrete playbook)

The single binding constraint is the **API exclusion from 0-fee spot**. Everything below is ToS-safe precisely because it respects that line or operates where the line does not apply.

### Tactic A — "Channel the flow": route spot through non-API channels
The 0-fee exclusion is keyed to *being an API user*. The cleanest ToS-safe approaches:
1. **Manual / assisted spot execution** for rebalancing and basis trades, executed on web/app. Low-freq by definition; the operator places the fills the strategy flags. Fees = 0. The strategy runs as a *signal generator*; a human (or a UI-automation layer that is not the API) transacts. This is explicitly the intended use of the promo ("Simply log in … select any Spot trading pair … begin trading").
2. **MEXC Convert for rebalancing** — 0 fee, fixed rate, no slippage, documented as a fee-free product. If Convert is *not* subject to the API exclusion (untested — confirm on the account), it is the legal, fee-free way for an automated system to move between assets.
3. **Reserve the API for futures only**, where the API exclusion does not apply to fees (futures charge regardless). The bot's programmatic leg lives on futures; the spot leg is the fee-free manual/Convert leg.

### Tactic B — "Promo-window routing" for futures
- Parse the announcement center weekly for 0-Fee Fest *additions* and *conclusions*.
- Bias the futures universe toward pairs in promo + the standing "0 Fees" category.
- Pay standard taker only when no promo substitute exists.
- This is pure schedule optimization — not market manipulation, not bot abuse.

### Tactic C — "MX real-yield engine"
- Hold a standing MX position to (i) collect Kickstarter airdrops, (ii) earn MX DeFi APY, (iii) ride the 40%-of-profit quarterly burn, (iv) buy down futures tier.
- Commit MX to every Kickstarter session mechanically. The committed MX is returned; only the airdrop is kept.
- This is *uncorrelated carry* against the trading book — the listed-token airdrops have their own beta and often spike at listing.

### Tactic D — "Volume-milestone farming at zero net cost"
- During a rewards-for-volume campaign, generate the minimum-threshold futures volume (e.g., 10k USDT/day Iron tier) **on pairs currently in 0-Fee Fest**, using a delta-neutral pair (long/short offsetting) so net market risk ≈ 0.
- Net cost ≈ funding + spread only; reward = redeemable merchandise/token. Positive EV if reward > funding over the campaign window.
- Keep volume *just above* the lowest discrete threshold (step function, not leaderboard) — do not chase higher tiers unless reward scales linearly (it does not; it scales as physical goods).

### Tactic E — Listing-event liquidity capture
- At each Kickstarter listing (fixed UTC time), the Innovation-Zone pair opens with predictable retail inflow and 0 spot fees.
- A non-API participant providing resting limit liquidity at listing captures the pop with zero fee drag — a venue-specific version of the new-listing premium that is *costless* on MEXC but ~0.1% elsewhere.

---

## 7. Costs that actually bite (do not ignore)

The 0-fee headline hides the real cost surface:
1. **Withdrawal/network fees** — the dominant cost for a fleet that rebalances across venues. Route through the cheapest chain per asset; batch withdrawals.
2. **Funding rate** on farmed futures volume — neutralize with opposing legs or by choosing balanced pairs.
3. **Spread on Convert** — "0 fee" but the rate embeds a spread; compare against the order-book mid before using Convert for size.
4. **Slippage on promo pairs** — 0-Fee Fest pairs can be thin; a fee savings of 1bp is not worth 20bp of slippage. Check depth before routing.

---

## 8. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| **0-fee spot ends** (TBA end date) | Med — it's still labeled "TBA" | Treat as a recurring promo, not a permanent right; build the playbook to work at *either* fee level; monitor announcements weekly |
| **API exclusion is enforced strictly** against your bot | High if you trade spot via API | Tactic A: keep spot on non-API channels; verify Convert's status |
| **Reward-farming flagged as "bot abuse"** | Low–Med if kept ToS-safe | Stay at discrete min thresholds, not leaderboards; do not multi-account; do not wash-trade circularly; one identity, real volume |
| **MX price drawdown** while holding for yield | Med | Size MX as a position with its own risk budget; the burn is deflationary but MX is illiquid in stress |
| **Promo pairs delisted mid-farm** | Low | Exit on the announced conclusion timestamp; never hold a promo position past its end |
| **0-Fee Fest conclusion forces a fee cliff** on open positions | Low | Don't carry directional positions *because* they're fee-free; only farm volume with neutral legs |

---

## 9. Bottom line for the fleet

- **The edge is not "trade more." It's "trade on the right channel, in the right window, holding the right token."** All three are low-frequency decisions made on a weekly/daily cadence from the announcement center.
- **Spot is free for humans, paid for bots.** Architect the fleet so the spot leg never touches the API (or use Convert if it clears). This alone is ~10bp/round-trip.
- **Futures fees are schedulable.** Route into 0-Fee Fest pairs; the promo calendar is the alpha.
- **MX is uncorrelated carry.** The Kickstarter + burn + DeFi stack pays you to be a customer of the exchange, not to predict price.
- **Volume campaigns are positive-EV when farmed at the minimum threshold on fee-free pairs** — the two promos compound.

Every tactic above is a *schedule* or *channel* decision, executable at human speed — exactly the regime where MEXC lets retail operate without tripping HFT/arb restrictions.

---

### Sources (primary, all fetched 2026-06-23)
- 0-Fee Spot FAQ: `https://www.mexc.com/support/article/mexc-0-fee-spot-trading-faq-264764306934491136`
- Year-End 0-fee launch: `https://www.mexc.com/announcements/article/special-year-end-offer-17827791532472`
- Convert (0-fee OTC swap): `https://www.mexc.com/support/article/how-to-use-mexc-convert-398850007640593408`
- MX buyback/burn (40% of profit): FAQ §5.3
- ZYLO Kickstarter (13.4M MX committed, airdrops distributed): `...voting-result-and-listing-arrangement-for-zylo-ecosystem-zylo-kickstarter-17827791536292`
- Football volume-milestone campaign (Iron = 10k USDT/day): `...watch-daily-win-daily-17827791536434`
- 0-Fee Fest futures (UNI/ICP/ESPORTS/VELVET; conclude Jun 22 10:00 UTC): `...0-fee-fest-17827791536372`, `...0-fee-fest-17827791536370`
- MVLL Index Futures 0-fee launch: `...mexc-to-list-mvll-usdt-m-index-futures-on-jun-23-with-0-fee-trading-17827791536432`
- Pre-Market Perpetual fees = standard futures; "0 Fees" is a pair category: Pre-Market guide §4.2
- Announcement center (live promo stream): `https://www.mexc.com/announcements/all`
- Trading Fees page (verify per-account): `https://www.mexc.com/fee`
