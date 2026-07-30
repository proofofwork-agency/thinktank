# 55 — Systematic point-farming on MEXC (Kickstarter + Launchpool) as a yield sleeve

**Agent:** 55/60 · **Scope:** MEXC Kickstarter and Launchpool as an **operational, low-risk, non-trading yield sleeve** — mechanics, ROI math with realistic annualization, sell-discipline implementation, the `KickstarterYieldSleeve` design, and risks. Composed against the **single-account MEXC envelope** (`16-mexc-tos-envelope.md` §5); explicitly **no multi-account splitting** (FAQ §4 tripwire).
**Stance:** NON-standard, low-frequency, capital-efficiency edge. This is *not* trading alpha — it is **scheduled participation in MEXC's own retail products**, executed at human cadence. Honors `16` §5; coordinates with **agent 24** (post-airdrop dump dynamics + Kickstarter as Strategy C), **agent 13** (MX real-yield, fees, channel routing), and **agent 38** (two-sleeve capital split + the `cash_return` benchmark this sleeve must clear).
**Status of evidence:** Kickstarter FAQ, Launchpool doc, and Earn page were **re-fetched live 2026-06-23** and are quoted verbatim where load-bearing. Per-session yield magnitudes are **calibrated to the two known data points** (XEFFY 30k USDT pool, ZYLO 13.45M MX committed — both via agent 24) and are **[HYPOTHESIS → backtest]**: track realized accrual on the account's own `/activity-reward-records` (`https://www.mexc.co/activity-reward-records?type=2`) for ≥90 days before sizing up. Binance Megadrop/Launchpool figures are public-knowledge industry ranges (direct fetch of `binance.com/en/support` returned empty for the FAQ endpoints) — flagged where used.

---

## 0. TL;DR (4 lines)

> MEXC runs two stacking point-farming products that pay you to hold tokens you might hold anyway: **Kickstarter** (commit MX, **not frozen**, vote, receive the listed token airdrop) and **Launchpool** (stake MX/USDT/other, **locked but redeemable anytime**, earn daily new-token rewards, **stacks with Kickstarter on the same MX**). Realistic per-session yield on committed MX is **~0.10–0.30%** → **~10–20% annualized gross** at ~1–3 sessions/week, but **paid in newly-listed tokens that themselves dump ~20–70% post-listing** (agent 24 §2), so realized return is **only captured by selling receipts at listing open** through a non-API channel (`13` §6 Tactic A); net of that discipline, expect **~5–12% annualized on MX** plus whatever the MX position itself does. The **`KickstarterYieldSleeve`** is a fleet-level scheduler (not an analyst signal): commit ≤100,000 MX to every eligible session, auto-dispose receipts at listing open, track realized-vs-benchmark ROI, halt if rolling 60-day realized yield falls below `cash_return` (`38` §6.4 / `cli.py:1061`). **Critical envelope constraints**: single account, one identity, **never split MX across accounts** (FAQ §4 explicit tripwire), one-time manual futures tick for eligibility — and note Launchpool §1 **excludes market makers / institutional accounts**, so this sleeve is **retail-KYC only**.

---

## 1. The two products (mechanics, verified 2026-06-23)

### 1.1 Kickstarter — commit MX (not frozen) → receive the new listing token

Source: [Kickstarter Event FAQ](https://www.mexc.co/learn/article/kickstarter-event-faq/1) (MEXC Learn, repr. in `24-airdrops.md` §3.1 and `13` §4).

- **Mechanism:** pre-launch voting event. Users commit MX to support a project; the winning project airdrops its token to all successful voters proportionally to valid committed MX.
- **Eligibility:** account must have completed **≥1 futures trade of any size** (open *and* close — "Completing a futures trade means both opening and closing a position"), and held **≥5 MX for 24 consecutive hours** before 16:00 UTC the day prior. (On the retail spot-only sleeve this is a **one-time manual futures tick** — see `24` §4 Strategy C.)
- **Snapshot rule (load-bearing for capital efficiency):** the *minimum* MX across 3 random intraday snapshots (UTC+8) sets your commit cap. Dropping below 5 MX at any snapshot → disqualified.
- **Commit range:** min **5 MX**, max **100,000 MX** per account.
- **Capital efficiency (the key fact):** *"The committed MX will be used to calculate rewards and will not be frozen."* You retain custody, fee-discount utility, and burn benefit for the entire commitment window — **zero opportunity cost on the MX itself**.
- **Reward formula:** `your_reward = (your_valid_MX / all_users'_valid_MX) × total_prize_pool`, scaled by a referral coefficient **V1=×1.0 → V7=×1.75** (V1 = no referrals, just hold MX; V2–V7 require inviting valid users who deposit ≥100 USDT and trade futures). **A retail operator with no referrals runs at V1=×1.0 — this is the realistic baseline.**
- **Multi-account tripwire (FAQ §4, verbatim):** *"If a single user commits a total of more than 100,000 MX across multiple accounts, the associated accounts may trigger the platform's risk control measures. Please proceed with caution."* → MEXC actively watches for split-account farming; the sleeve is **structurally single-account**.

### 1.2 Launchpool — stake designated tokens → earn daily new-token rewards

Source: [What Is Launchpool?](https://www.mexc.com/learn/article/what-is-launchpool-/1) (MEXC Learn, fetched 2026-06-23). **This product is NOT covered by agents 13/24/38 — the load-bearing novelty is below.**

- **Mechanism:** stake a designated token (MX, USDT, or a project-specific token) into a pool; earn a stream of the newly-listed token, distributed daily.
- **Capital rule (differs from Kickstarter):** *"Tokens staked for Launchpool events typically require a minimum amount. During the event period, **staked tokens will be locked**."* **BUT** §2.3 + §3.1 confirm: *"You can redeem staked tokens at any time. Tokens will be immediately transferred to your spot account upon redemption."* → effectively **flexible-redeem locked**, not frozen — funds are at-risk only between redeem-click and settlement (seconds).
- **Eligibility (load-bearing ToS constraint):** *"Market makers, institutional accounts, and users from restricted countries/regions are prohibited from participating in this event."* Combined with `16` §2.3 (futures API auto-trading is institution-only / KYB), this **structurally ties the sleeve to the retail-KYC track** — if rapana ever migrates to a KYB/institutional MEXC account, Launchpool access is forfeit.
- **Reward formula:** `daily_reward = (your_daily_avg_staked / all_users_daily_avg_staked) × daily_prize_pool`. Hourly interest calc; settles T+1h / T+1d / one-shot at end (event-specific). **Stakes <1h generate no interest.**
- **Stacking (the dual-reward lever, §3.3 verbatim):** *"Staked MX tokens can simultaneously participate in the Kickstarter event, allowing you to enjoy dual rewards."* → **MX staked in Launchpool also counts toward Kickstarter eligibility.** This is the capital-efficiency apex: one MX position, two parallel reward streams. Confirmed also by Kickstarter §2 ("the minimum of all MX amounts snapshotted over the consecutive 24 hours will be used") — staked MX is still *your* MX.

### 1.3 MEXC Flexible Savings / Hold-and-Earn (the third leg, briefly)

Earn page (`mexc.com/earn`, fetched 2026-06-23) lists Flexible / Fixed Savings, On-Chain Earn, Hold-and-Earn (auto-earn on spot balance), Futures Earn. **Steady-state ~1–3% APR on USDT/USDC (peer-CEX parity); "up to 600% APR" = new-user promo on capped principal** (see `38` §2 row C1). Flexible USDT is the natural parking spot for the *non-MX* portion of the sleeve budget. **Counterparty stays MEXC** — see `38` §5; do not over-concentrate.

### 1.4 Comparison: MEXC vs Binance Megadrop / Binance Launchpool / Bitget PoolX

Public-knowledge industry comparison (Binance FAQ endpoint returned empty on fetch; magnitudes are analyst ranges, **[HYPOTHESIS]** — verify per-campaign on the live UIs before sizing).

| Product | Capital lock | Reward token | Typical per-drop ROI on committed capital | Capital efficiency | Notes |
|---|---|---|---|---|---|
| **MEXC Kickstarter** ⭐ | **None** (MX not frozen) | newly-listed token | ~0.10–0.30% per session | **Highest** | Retain MX custody + burn + fee discount; max 100k MX |
| **MEXC Launchpool** | Locked, **flexible-redeem** | newly-listed token (daily stream) | ~5–30% APR headline (pool-dependent) | High (instant redeem) | Stacks with Kickstarter on the same MX (§1.2) |
| **Binance Megadrop** | **Hard-locked BNB ~30d** + Web3-wallet tasks | newly-listed token (larger projects) | historically ~5–25% on locked BNB per campaign, **high variance** | Low (hard lockup) | Larger pool sizes; task component adds friction |
| **Binance Launchpool** | Locked BNB/FDUSD, flexible redeem | newly-listed token (daily) | ~3–15% APR on BNB | Medium | Closest analog to MEXC Launchpool |
| **Bitget PoolX** | Locked, flexible redeem | newly-listed token | ~5–20% APR | Medium | Similar mechanics; smaller venue |

**The asymmetry that matters:** MEXC Kickstarter is the **only** major-venue point-farm where the committed asset is *not* locked. That makes it strictly dominant on capital efficiency for an operator who already has a thesis on MX. The cost is **smaller prize pools** (XEFFY ~$30k USDT; agent 24 §3.2) vs Binance-scale drops — the per-session percentage is similar, but MEXC's reward token is a higher-beta small-cap (more upside, more downside — sell-discipline matters more, not less).

---

## 2. ROI math — realistic annualized (the load-bearing table)

### 2.1 Per-session yield on committed MX (Kickstarter, V1 = ×1.0 baseline)

Using the two verified data points (agent 24 §3.2): **XEFFY** pool = 30,000 USDT; **ZYLO** total commitment = 13,449,696 MX (~$23.3M at MX=$1.73). Generalized:

```
per_session_yield = pool_usd / total_committed_usd
                  = pool_usd / (total_committed_MX × MX_price)
```

| Scenario | Pool (USDT equiv) | Total committed MX | MX price | Per-session yield |
|---|---|---|---|---|
| **Hot session (ZYLO-like)** | $30,000 | 13.45M | $1.73 | **0.129%** |
| **Average session** | $30,000 | 10M | $1.73 | 0.173% |
| **Cold session (low crowding)** | $30,000 | 5M | $1.73 | 0.347% |
| **Crowded session** | $30,000 | 20M | $1.73 | 0.087% |
| **Big-pool event** | $100,000 | 15M | $1.73 | 0.385% |

### 2.2 Annualized (gross, before token-dump haircut)

MEXC lists ~1–3 Kickstarter sessions/week (~104–156 sessions/year, agent 24 §3.2). Range:

```
annualized_gross = per_session_yield × sessions_per_year
```

| Per-session | Sessions/yr | Annualized gross |
|---|---|---|
| 0.10% (crowded) | 130 | **~13%** |
| 0.17% (average) | 130 | **~22%** |
| 0.25% (warm) | 130 | **~33%** |
| 0.35% (cold/big-pool) | 130 | **~46%** |

**These numbers are gross of the received-token dump.** That haircut is the entire game.

### 2.3 The dump haircut (load-bearing — received tokens are not "yield" until sold)

Agent 24 §2 establishes: ~50–85% of received airdrop tokens are sold within 7 days; median drawdown **−20 to −40% in weeks 1–4**; ~70% of airdropped tokens never profit holders. The received Kickstarter tokens *are* airdropped tokens — same dynamics apply.

**Sell-discipline scenarios** (assume Kickstarter-listed tokens behave like the agent-24 sample: −20% w1, −40% w4 if held):

| Disposition | Realized value vs nominal | Annualized net on MX |
|---|---|---|
| **Sell at listing open (T0 ±5 min, non-API)** | ~95–100% of nominal (pop + slippage) | **~12–22%** |
| Sell at T+24h | ~80–90% of nominal | ~10–18% |
| Hold 1 week | ~60–80% of nominal | ~8–14% |
| Hold 1 month (the trap) | ~40–60% of nominal | ~5–11% |
| Hold to "see how it does" | often ≤30% of nominal | **<5% or negative** |

**The honest headline: with sell-at-open discipline, expect ~10–20% annualized net on committed MX. Without it, expect ~3–8%.** The yield is a *behavioral* edge, not a market edge.

### 2.4 Capital-efficiency vs stablecoin alternatives (the real benchmark)

This is what agent 38 §2 calls the "honest baseline." Kickstarter yield does **not** exist in a vacuum — the MX you commit has its own opportunity cost and its own price risk.

| Sleeve | Capital | Net APY | Capital lock | Price risk |
|---|---|---|---|---|
| Stablecoin real-yield (sUSDS / Aave) | USDC/USDS | **~3–4%** | none | depeg-only (agent 21) |
| MEXC Flexible USDT | USDT | ~1–3% | none | MEXC counterparty |
| **MX-Kickstarter (sell-at-open)** | MX | **~10–20%** | **none** (MX not frozen) | **MX price drawdown** |
| MX-Kickstarter + Launchpool stack | MX | ~12–25% (additive) | Launchpool-leg locked, flexible-redeem | MX price drawdown |
| Naked hold MX (no farming) | MX | MX burn ≈ deflationary, no coupon | n/a | MX price drawdown |

**Reading:** Kickstarter dominates stable-yield **only if** (a) you have a separately-justified MX position (do not buy MX *to farm* — that conflates a directional bet with a yield sleeve), and (b) you actually execute the sell discipline. Otherwise stablecoin real-yield (~3–4%, agent 38 §2) is the correct default.

### 2.5 Pool-crowding dynamics — the yield decays

The reward formula is **zero-sum across participants**: `your_share = your_MX / all_MX`. As MEXC grows and total committed MX rises, per-MX yield falls mechanically. Kickstarter FAQ §5/§6 verbatim: *"If overall commitment increases significantly, your proportional share may decrease."* This is a structural headwind — assume **per-session yield halves every 12–18 months** at current MEXC user growth, and re-tracked realized yield quarterly. If trailing-60d realized yield < `cash_return` (`cli.py:1061`), halt the sleeve.

---

## 3. The honest discipline — sell-at-listing-open, operationalized

### 3.1 Why this is the single most important rule

Agent 24 §1: airdrop recipients have **zero cost basis and immediate liquidity**, so the dump is structural, not sentiment. The Kickstarter receipt is *exactly* such an airdrop — your yield exists only as a mark-to-listing-pop if you liquidate at open. Holding the receipt converts yield into the **−20 to −70% post-claim drift** the agent-24 sample documents.

### 3.2 How to execute (channel-aware, ToS-safe)

The receipt is a *spot* sale of a newly-listed token. Three ToS-safe channels (in order of preference):

1. **MEXC Convert** (preferred for small receipts) — 0 fee, fixed rate, no slippage (`13` §2.1, `https://www.mexc.com/support/article/how-to-use-mexc-convert-398850007640593408`). Convert the received token → USDT immediately on receipt. Convert's API-exclusion status is *unverified* — if Convert works for the API key, this is fully automatable; if not, route manually.
2. **Manual / web / app spot sale** (fallback) — preserves 0-fee spot (`13` §1, §6 Tactic A). The bot emits a *signal*; a human clicks. Low-frequency by definition (1–3 receipts/week).
3. **API spot sale (last resort)** — trips the `13` §1.3 API exclusion from 0-fee spot. Only use if receipt size justifies the fee drag, and never in the ±5 min listing-open blackout (`16` §5.1 event rule; first-tick chaos + 30027/30028 halt risk per `10` §2).

### 3.3 Timing — when "listing open" actually means

Kickstarter listings have an **announced fixed UTC time** (e.g., ZYLO: "Trading in the Innovation Zone: Jun 23, 2026, 12:00 UTC", per agent 13 §5.2). The receipt hits the spot wallet **before** listing open. The optimal sell window is **listing-open + 30s to +5 min** — late enough to capture any pop from retail inflow, early enough to dodge the w1 dump. This is the **opposite** of `16` §5.1 event-concentration trap: a *recipient* selling a receipt is **normal retail behavior** (the entire cohort does it), not a synchronized arb burst.

---

## 4. `KickstarterYieldSleeve` — design

### 4.1 Concept

A **fleet-level scheduler** (not an analyst `Signal` — see `24` §5.2 and `38` §6.4). Lives alongside `rapana/fleet/kickstarter.py` (already proposed by agent 24) — this agent specifies the concrete class. It commits MX to every eligible session, disposes receipts via Convert/manual, and tracks realized ROI vs `cash_return`.

### 4.2 Config (YAML, mirrors `38` §6.4 touch points)

```yaml
kickstarter_yield_sleeve:
  enabled: true
  account: <single KYC'd retail MEXC account>   # retail ONLY — Launchpool §1 excludes MM/institutional
  mx_budget: 100000                              # FAQ §4 hard cap; NEVER split across accounts
  mx_source: existing_position                   # never "buy MX to farm" — see §2.4
  eligibility_futures_tick: manual_one_time      # one-off, not automated futures (16 §2.3)
  referral_coefficient: V1                       # x1.0; do NOT referral-farm (ToS tripwire)
  disposition:
    channel: convert                             # convert | manual_spot | api_spot
    timing: listing_open_plus_30s                # not in the ±5m blackout
    target: USDT
  launchpool_stack: true                         # stake same MX in parallel Launchpool (§1.2 dual-reward)
  halt:
    rolling_60d_realized_yield_below: 0.035      # = cash_return (38 §6.4); halt if underperforming stables
    mx_drawdown_from_entry_above: 0.35           # the MX position itself is the real risk
  tracking:
    record_every_session: true                   # log to /activity-reward-records mirror
    benchmark: cash_return                       # cli.py:1061
```

### 4.3 State machine (pseudocode)

```
class KickstarterYieldSleeve:
    """Fleet-level scheduler. Emits NO per-symbol Signal; modifies fleet config + cron."""

    STATES = {"DISABLED", "AWAITING_SESSION", "COMMITTED", "AWAITING_LISTING",
              "RECEIVED", "DISPOSED", "HALTED"}

    def on_new_session_announcement(self, session):
        if not self._eligible(): return            # ≥1 past futures trade, ≥5 MX held 24h
        commit = min(self.cfg.mx_budget, self.mx_spot_balance)
        self._commit_mx(commit, session.id)        # manual web action or sanctioned API endpoint
        self.state = "COMMITTED"
        # if launchpool_stack and a parallel Launchpool exists, the same MX counts (§1.2)

    def on_listing_open(self, session):
        receipt = self._fetch_receipt(session.token)  # from spot balance
        if receipt.qty <= 0: return
        self.state = "RECEIVED"
        self._dispose(receipt, channel=self.cfg.disposition.channel,
                      timing=self.cfg.disposition.timing)
        self._record_session(session, receipt)     # realized USDT, MX_opcost, timestamp
        self.state = "DISPOSED"
        self._check_halt()                         # rolling-60d realized vs benchmark

    def _check_halt(self):
        realized_60d = self._rolling_realized_yield(window_days=60)
        mx_dd = self._mx_drawdown_from_entry()
        if realized_60d < self.cfg.halt.rolling_60d_realized_yield_below \
           or mx_dd > self.cfg.halt.mx_drawdown_from_entry_above:
            self.state = "HALTED"
            self._alert("Kickstarter sleeve halted: realized={realized_60d} "
                        "MX_dd={mx_dd} — review whether MX position itself should be exited")
```

### 4.4 Realized-ROI accounting (the part most operators skip)

Every session logs (to `rapana/journal/` or a new `rapana/fleet/kickstarter_ledger.jsonl`):

```
{
  "session_id": "ZYLO-2026-06-23",
  "committed_mx": 100000,
  "mx_price_at_commit": 1.73,
  "commit_usd_equiv": 173000.0,
  "reward_token": "ZYLO",
  "reward_qty": 1234.56,
  "reward_nominal_usd_at_listing_open": 43.91,    // pre-dump nominal
  "realized_usd_after_disposition": 41.85,         // post-dump realized
  "disposition_channel": "convert",
  "disposition_lag_seconds": 42,
  "mx_opcost_30d_usd": 0.0,                        // MX not frozen → ~0
  "realized_yield_pct": 0.0242,                    // realized_usd / commit_usd_equiv
  "nominal_yield_pct": 0.0254,                     // pre-dump nominal
  "dump_haircut_pct": 0.047,                       // 1 - realized/nominal
  "timestamp": "2026-06-23T12:01:18Z"
}
```

**The two numbers that matter:** `realized_yield_pct` (what you actually kept) and `dump_haircut_pct` (how much the post-receipt drift cost you). If `dump_haircut_pct` trends above ~15% over 30 days, the sell-discipline execution is slipping — fix the channel/timing before chasing yield.

### 4.5 ToS / envelope check (`16` §5.1 row-by-row)

| Envelope row | Status |
|---|---|
| MEXC's own product, invited use | ✅ "bring airdrop benefits to MEXC users" (FAQ §1); Launchpool §1 explicitly invites retail users |
| Single account, one identity | ✅ **CRITICAL:** FAQ §4 explicit tripwire on >100k MX across accounts; one account only |
| No multi-account splitting | ✅ structural; never split MX |
| Eligibility futures trade | ⚠️ one-off manual tick; **not** automated futures (which is KYB-gated, `16` §2.3) |
| Sell-at-open of receipts | ⚠️ spot sale / Convert (non-API preferred to preserve 0-fee spot, `13` §1/§6); not in ±5m blackout |
| Order rate / cancel ratio | ✅ N/A — no order-book interaction in the commit phase; only one spot sale per receipt |
| Event blackout ±5 min | ✅ dispose at +30s to +5min *after* open, as a recipient (cohort behavior, not synchronized arb) |
| Retail-KYC track only | ⚠️ Launchpool §1 **excludes MM/institutional** — if rapana ever migrates to KYB, Launchpool access forfeit; Kickstarter ToS status under KYB unverified |

**Verdict: ToS-safe by construction** for the retail-KYC, single-account, non-split layout. The two operational touchpoints are (1) route the receipt sale through non-API channels to preserve 0-fee spot, and (2) the one-time manual futures tick for eligibility — *not* automated futures.

---

## 5. Touch points in the repo (file:line)

| Change | Where | What |
|---|---|---|
| Sleeve module | new `rapana/fleet/kickstarter.py` (proposed by `24` §5.2) | Concrete `KickstarterYieldSleeve` class (§4.3) + ledger (§4.4) |
| Config schema | `rapana/config.py` (wherever fleet YAML is loaded) | Add `kickstarter_yield_sleeve` block (§4.2); gated on `account.track == "retail_kyc"` |
| Session calendar source | new `rapana/data/mexc_kickstarter_calendar.py` | Scrape-free: consume official Telegram `t.me/MEXC_OfficialAnnouncements` (`10` §3.3, `24` §6) + `mexc.com/announcements/all` for commit-open / listing-open timestamps and pool sizes |
| Realized-yield ledger | new `rapana/fleet/kickstarter_ledger.jsonl` + mirror read from `/activity-reward-records?type=2` | One row per session (§4.4 schema) |
| Halt gate | integrate with `rapana/fleet/autopilot.py` | Honor sleeve `HALTED` state; surface in fleet health dashboard |
| Benchmark wire | `rapana/cli.py:1061,1077` (`--cash-return`) | Sleeve halt threshold defaults to `cash_return` (set `cash_return=0.035` per `38` §6.4) |
| Signal surface (optional) | `rapana/agents/yield_strategist.py:13-31` (currently neutral-by-default per `38` §6.4) | Emit a low-conviction `"yield"` Signal on MX when sleeve is `COMMITTED` (strength ≤ 0.15) — never overrides directional alpha |
| Sleeve does NOT touch | `rapana/agents/*.py` per-symbol analysts, `rapana/fleet/execution.py` order-path | This is fleet config + cron, not a trading strategy |

---

## 6. Free data sources (all keyless, all free)

| Need | Source | URL |
|---|---|---|
| **Kickstarter mechanics** (eligibility, commit caps, multi-account warning) | MEXC Learn | https://www.mexc.co/learn/article/kickstarter-event-faq/1 |
| **Launchpool mechanics** (lock + flexible redeem, dual-stack, MM exclusion) | MEXC Learn | https://www.mexc.com/learn/article/what-is-launchpool-/1 |
| **MEXC Earn products** (Flexible/Fixed/On-Chain/Hold-and-Earn) | MEXC Earn landing | https://www.mexc.com/earn |
| **Kickstarter session calendar** (commit open, listing time, pool size, total committed) | Official Telegram + announcement center | `t.me/MEXC_OfficialAnnouncements` · https://www.mexc.com/announcements/all |
| **Per-account reward history** (the ground truth for realized-yield tracking) | MEXC reward records | https://www.mexc.co/activity-reward-records?type=2 |
| **MX price + 40%-of-profit quarterly burn** | FAQ §5.3 (burn) + exchange ticker (price) | https://www.mexc.com/exchange/MX_USDT |
| **Post-listing OHLCV for backtesting the dump haircut** | MEXC free historical | `mexc.co/zh-CN/market-data-download` (`10` §6) + `GET /api/v3/klines` |
| **Comparison venue — Binance Megadrop** (industry comparison only; verify on live UI) | Binance announcement center | https://www.binance.com/en/support/announcement/binance-megadrop |
| **MEXC Convert** (preferred receipt-disposition channel) | MEXC support | https://www.mexc.com/support/article/how-to-use-mexc-convert-398850007640593408 |

---

## 7. Risk register (honest, prioritized)

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **Received tokens dump before disposition** (the central risk) | **Very high** | High | Sell-at-listing-open via non-API channel (§3.2); monitor `dump_haircut_pct` (§4.4); halt sleeve if rolling > 15% |
| 2 | **MX price drawdown while committed** | Medium | **Very high** (MX is the real position) | Sleeve is carry *on an existing* MX thesis — never buy MX *to farm* (§2.4); halt on MX_dd > 35% from entry; size MX with its own risk budget (`13` §8) |
| 3 | **Pool crowding dilutes per-session yield** as MEXC grows | **Certain over time** | Medium | Track realized yield quarterly; halt if rolling-60d < `cash_return`; FAQ §5/§6 acknowledge this explicitly |
| 4 | **Multi-account Kickstarter farming** | — (do not do) | Fatal (account freeze) | FAQ §4 explicit tripwire; structural single-account; never split MX (§1.1) |
| 5 | **Receipt disposition trips 0-fee-spot API exclusion** | Medium (if via API) | Low (fee drag) | Route through Convert or manual web (§3.2); Convert's API-exclusion status unverified — test before automating |
| 6 | **Listing-open chaos: 30027/30028 halts** on the receipt sale | Medium | Low (you're a seller, not chasing the pop) | Dispose at +30s to +5min after open, not in the first-tick blackout (`16` §5.1, `10` §2) |
| 7 | **Launchpool §1 MM/institutional exclusion** | — | Sleeve constraint | Stay on retail-KYC track; if migrating to KYB, Launchpool access is forfeit (Kickstarter status under KYB unverified) |
| 8 | **Eligibility futures tick escalates into "automated futures"** flag | Low if one-off | High (KYB-gated, `16` §2.3) | Strictly one-time manual tick; document it in the journal; never automate |
| 9 | **Reward-token distribution delayed past listing open** | Low–Med | Medium (sell window slips) | Track `disposition_lag_seconds`; if distribution chronically misses listing-open, switch disposition to T+24h marketable-limit |
| 10 | **Referral-coefficient farming temptation** (V2–V7) | Behavioral | High (ToS tripwire on manufactured referrals) | Run at V1=×1.0 baseline; never referral-farm — it is the multi-account tripwire's first cousin |
| 11 | **Yield magnitudes are calibrated to 2 data points, not peer-reviewed** | — | Medium | Verify against 90d of own `/activity-reward-records` before sizing up; same discipline as `10` §6 |

---

## 8. Coordination notes (fleet)

- **Agent 24** owns the post-airdrop *price-dynamics* edge (Strategies A: claim-window veto, B: post-washout accumulate). This agent owns the **yield-sleeve** operationalization (Strategy C, deepened). No overlap; complementary.
- **Agent 13** owns the fee/channel surface. The sleeve's disposition-channel choice (§3.2) consumes `13` §6 Tactic A (non-API routing) verbatim.
- **Agent 38** owns the capital-split architecture. The Kickstarter sleeve is the **Carry sleeve** in `38` §6.1's diagram (the ~0–5% allocation); this agent supplies the concrete class. The sleeve's halt threshold (`cash_return`) is wired to `38` §6.4 / `cli.py:1061`.
- **Agent 16** owns the envelope. The sleeve is ToS-safe by construction (§4.5) but inherits the **retail-KYC-only** constraint from Launchpool §1 — flag if rapana ever considers KYB migration.

---

## 9. Sources (consolidated; all fetched 2026-06-23 unless noted)

- S1 — MEXC, "Kickstarter Event FAQ" (mechanics, eligibility, commit caps, MX-not-frozen, multi-account risk-control warning §4, reward coefficient table V1–V7, snapshot rule). https://www.mexc.co/learn/article/kickstarter-event-faq/1
- S2 — MEXC, "What Is Launchpool?" (KYC required, **MM/institutional excluded** §1, lock-but-flexible-redeem §2.3/§3.1, **dual-stack with Kickstarter on same MX** §3.3, daily reward formula §3.4, hourly interest calc §3.5). https://www.mexc.com/learn/article/what-is-launchpool-/1
- S3 — MEXC, "MEXC Earn" landing page (Flexible/Fixed/On-Chain/Hold-and-Earn/Futures Earn; "up to 600% APR" new-user promo; "Hold and Earn" auto-earn on spot balance). https://www.mexc.com/earn
- S4 — MEXC, "How to Use MEXC Convert" (0-fee OTC swap, fixed rate, no slippage — preferred receipt-disposition channel). https://www.mexc.com/support/article/how-to-use-mexc-convert-398850007640593408
- S5 — MEXC announcement center (live Kickstarter/Launchpool session stream: commit-open, listing-open, pool size, total committed). https://www.mexc.com/announcements/all
- S6 — MEXC reward records (per-account realized-yield ground truth). https://www.mexc.co/activity-reward-records?type=2
- S7 — MEXC, ZYLO Kickstarter voting result (13,449,696 MX total committed — pool-crowding anchor). cited via `13` §4 and `24` §3.2
- S8 — Binance Megadrop announcement index (industry comparison only; direct FAQ fetch returned empty — magnitudes are public-knowledge analyst ranges, flagged **[HYPOTHESIS]** in §1.4). https://www.binance.com/en/support/announcement/binance-megadrop
- Cross-ref: `24-airdrops.md` §2 (post-claim dump magnitudes — the haircut table §2.3), §3 (Strategy C mechanics — this agent deepens), §4 (ToS row-by-row — this agent reuses); `13-mexc-fees-promos.md` §1/§6 (API exclusion + non-API routing), §4 (MX real-yield), §5.2 (Kickstarter cycle); `38-defi-yield.md` §2 (stablecoin real-yield baseline), §6.1/§6.4 (sleeve architecture + `cash_return` wire); `16-mexc-tos-envelope.md` §2.3 (futures = KYB), §5.1 (event blackout, single-account), §5.5/§5.6.3 (position-limit evasion — the multi-account tripwire's parent rule); `10-mexc-listings.md` §2/§6 (listing-event behavior, 30027/30028 halts, free historical download).

---

## Summary (≤4 lines)

MEXC runs two **stackable point-farm products** — **Kickstarter** (commit MX, **not frozen**, max 100k MX/account, FAQ §4 hard-bans splitting) and **Launchpool** (stake MX/USDT, locked-but-instantly-redeemable, **stacks dual-reward on the same MX** per §3.3, **excludes MM/institutional** per §1) — yielding **~10–20% annualized gross on committed MX** (~0.10–0.30% × ~130 sessions/yr), but **paid in newly-listed tokens that themselves dump −20–70% post-listing** (agent 24 §2), so realized return depends entirely on **sell-at-listing-open discipline via non-API channel** (`13` §6 Tactic A; Convert preferred). The **`KickstarterYieldSleeve`** is a fleet-level scheduler (not a per-symbol Signal): commit ≤100k MX to every eligible session, dispose receipts at +30s–+5min post-open, log realized-vs-nominal yield + dump-haircut per session, and **halt when rolling-60d realized yield < `cash_return`** (`38` §6.4 / `cli.py:1061`, set to 0.035) **or MX drawdown > 35%**. **Critical envelope constraints**: single account, one identity, never split MX (FAQ §4 tripwire → `16` §5.6.3), one-off manual futures tick for eligibility (not automated), retail-KYC only. The yield is a **behavioral edge** (sell discipline) layered on a separately-justified MX position — it is **not** a reason to acquire MX, and **not** a substitute for the ~3–4% stablecoin real-yield floor (agent 38 §2) which remains the capital-preservation default.
