# 46 — LLM Tokenomics / Rug-Dilution-Risk Filter (Universe DEFENSE)

**Agent:** 46/60 — Tokenomics contract-risk research (DEFENSIVE exclusion edge)
**Scope:** `rapana/universe/scout.py`, `rapana/universe/ranker.py`, `rapana/feeds/`, `rapana/agents/macro.py`, `rapana/data/store.py:13-43`, `.env.example:61-62` (dead `CRYPTORANK_API_KEY`)
**Thesis:** On a venue that lists **1,882 coins / 2,400 pairs** (CoinGecko, research/agents/17 §0) — dominated by small-caps, meme, and narrative tokens — the **default base-rate is loss**. Peer-reviewed work shows the modal outcome for a sub-$50M-FDV newly-listed token is a **>90% drawdown within 90 days** (La Morgia 2023; Nghiem 2021; Luo 2025 — all cited in research/agents/17 §1), driven by two mechanical forces: **inventory concentration (insider holdings) and attention fabrication** (Luo, Ding, Xu 2025). A momentum-following Scout (research/agents/06 §b — score is literally `momentum/volatility`, `ranker.py:77`) **systematically selects into** the exact pump→dump→die names: their 30h momentum and 24h volume are *inflated* by the pump. The cheapest, highest-evidence edge is therefore **defensive — refuse the rug/dilution/honeypot-prone names before they reach the order path.** This agent designs a `TokenomicsRiskFilter` that audits Scout candidates against free contract-risk data (GoPlus Security API — verified live this session) + supply data (Tokenomist) + liquidity/age (DexScreener), emits a deterministic risk score, and **hard-excludes the structural-rug names / caps the marginal ones**. The LLM is fenced to an *advisory summary role only* — it never edits the score, the exclude decision, or any size (per research/agents/32: TradeTrap `2512.02261` proves LLM judgment must stay out of the order path; AI-Trader `2512.10971` names risk-control as *the* cross-market differentiator).

> **Differentiation from siblings:** Agent **22 (unlocks)** covers the **supply SCHEDULE** (cliff dates, recipient class, unclaimed overhang) — a *time-bounded event* edge. Agent **46 (this)** covers the **contract / structural** risk surface (honeypot, mint authority, transfer tax, holder concentration, liquidity depth, pool age, anonymous team) — a *standing-state* edge. They share the overhang concept (Tokenomist Released-vs-Circulating) but 46 is the broader defensive net catching rug/honeypot/dilution names that 22's unlock-only view cannot see (a freshly-minted honeypot has no "unlock schedule" but is a guaranteed loss). Agent **6 (universe)** is the selection framework; 46 is a concrete exclusion layer plugging into Scout — the contract-risk generalisation of edge #5 ("low-float / unlock-approaching tokens") in research/agents/06 §(c). No overlap with agents 17/35 (attention/on-chain-valuation are *directional* edges; this is *exclusion*).

---

## (a) The risk surface — what kills a long-only small-cap position

A spot-only fleet can only be *long* and can only *avoid* (research/agents/17 §3.2 — you cannot reliably borrow/short the MEXC long tail). So the loss taxonomy is the set of mechanisms that convert a long position into a permanent loss. Grouped by whether they are **contract-verifiable** (deterministic, GoPlus/Tokenomist/DexScreener-readable) or **behavioural** (LLM-assistable, not contract-anchored):

| Risk | Mechanism | Contract-verifiable? | Primary data source |
|---|---|---|---|
| **Honeypot** | Contract allows buy but blocks/penalises sell. You can enter, never exit. | ✅ Yes | GoPlus `is_honeypot`, `cannot_buy`, `sell_tax` |
| **Mint authority** (`is_mintable`) | Owner can mint unlimited new supply → instantaneous dilution to zero. The canonical "rug" primitive. | ✅ Yes | GoPlus `is_mintable`, `hidden_owner` |
| **Modifiable tax / slippage** | Owner can raise `buy_tax`/`sell_tax` after you enter → de-facto honeypot. | ✅ Yes | GoPlus `slippage_modifiable`, `personal_slippage_modifiable` |
| **Pausable / blacklisted** | Owner can freeze transfers or blacklist specific wallets → position trapped. | ✅ Yes | GoPlus `transfer_pausable`, `is_blacklisted`, `is_whitelisted` |
| **Hidden / takeback ownership** | `hidden_owner` or `can_take_back_ownership` lets the deployer reclaim the contract → re-mint, re-tax. | ✅ Yes | GoPlus `hidden_owner`, `can_take_back_ownership`, `owner_change_balance` |
| **Holder concentration** (insider/`dev` wallet) | Single non-exchange holder owns a large fraction → mechanistic dump on retail inflow (Luo 2025 "copy-trading" exit liquidity; Krause $TRUMP ~80% insider). | ✅ Yes | GoPlus `holders[]` + `is_locked` flags |
| **Unclaimed overhang** | Released-but-not-circulating supply sitting in stakeholder wallets → persistent selling pressure. | ✅ Yes | Tokenomist Released vs Circulating |
| **Scheduled dilution cliff** | Large % of float unlocking in a single event. | ✅ Yes (via 22) | Tokenomist unlock-events |
| **Thin / brand-new pool** | Sub-$50k liquidity or <24h-old pair → un-tradeable, exit impossible, rug-magnet. | ✅ Yes | DexScreener `liquidity.usd`, `pairCreatedAt` |
| **Closed source** | Contract not verified → cannot audit any of the above. | ✅ Yes | GoPlus `is_open_source` |
| **Anonymous team** | No doxxed team/KYC → no accountability, rug with impunity. | ⚠️ Behavioural | LLM-assist (whitepaper/socials) |
| **Unrealistic-APY / Ponziomics** | "Stake for 400% APY" tokenomics → mathematically collapses on outflow. | ⚠️ Behavioural | LLM-assist (whitepaper) |

**The key insight:** the top 9 rows are **deterministic and contract-anchored** — they are *bits in the contract state*, readable in one API call, falsifiable, and PIT-clean. They are the load-bearing inputs. The bottom 2 (anonymous team, ponziomics) are genuinely LLM-friendly but **must remain advisory** — a hallucinated "anonymous team" flag that excludes a legitimate token is a real cost, so they can never be the sole trigger for exclusion (see §d, the fencing rule).

---

## (b) Evidence — magnitudes & predictability

### b.1 The contract-risk signals are real, free, and live-verified

**GoPlus Security API** was fetched live this session and returns the full risk record per contract, **free, no API key**:

```
GET https://api.gopluslabs.io/api/v1/token_security/1?contract_addresses=0xdAC17F958D2ee523a2206206994597C13D831ec7
→ 200 OK, JSON with: is_open_source, is_proxy, is_mintable, owner_address/owner_percent,
   is_honeypot, transfer_pausable, cannot_buy, slippage_modifiable, personal_slippage_modifiable,
   is_blacklisted, is_whitelisted, is_anti_whale, sell_tax, buy_tax, trading_cooldown,
   transfer_tax, personal_slippage_modifiable, hidden_owner, can_take_back_ownership,
   honeypot_with_same_creator, creator_address/creator_percent, selfdestruct, external_call,
   holder_count, holders[](address, percent, is_locked, is_contract), is_in_cex, is_in_dex,
   total_supply, trust_list
```

(Verified live for the USDT contract: `is_mintable:1, is_open_source:1, slippage_modifiable:1, transfer_pausable:1, is_blacklisted:1, holder_count` + top-10 holders each with `is_locked` flag.) Supported chains — **43 chains, confirmed** via `GET /supported_chains`: Ethereum(1), BSC(56), Solana, Arbitrum(42161), Polygon(137), Base(8453), Tron, opBNB, zkSync, Linea, Optimism, Avalanche, Mantle, Scroll, Sonic, Berachain, World Chain, Monad, … — **every chain MEXC lists tokens on**. The EVM endpoint is confirmed working; the Solana endpoint exists at a separate path (`/sol-token-security`) and must be endpoint-verified at integration time (its exact query shape was not resolved this session — flag in §h).

**DexScreener API** — free, 60 req/min, no key (verified live, `docs.dexscreener.com/api/reference`). The `/latest/dex/search?q=<SYMBOL>` and `/tokens/v1/{chainId}/{tokenAddress}` endpoints return per-pair: `liquidity.usd`, `fdv`, `marketCap`, `pairCreatedAt`, `txns` (buys/sells by timeframe), `volume`, `priceChange`, `info.socials/websites`, `baseToken.address`. This is **both** the MEXC-symbol→(chain,contract) resolver *and* the liquidity/age/pool-depth read in one call.

**Tokenomist** — free trial (50 tokens, 1y backward, 120 req/min; research/agents/22 §c). Supplies Released/Circulating/Locked/TBD-Locked, unlock-event cliffs, `committedClaim` (HYPE-style under-claim). Methodology (verified live, `docs.tokenomist.ai/methodology/supply-metrics`): **"Compare Released Supply to Circulating Supply. A large gap means insiders are holding a significant amount of claimable tokens that *could* enter the market at any time."**

### b.2 Predictability — the signals map to *mechanical* losses, not statistical patterns

Unlike price-prediction edges (which fail OOS — research/agents/32), these risks convert to losses **by construction of the contract**, not by market behaviour:

1. **`is_honeypot == 1` → P(loss | you enter) ≈ 1.** You literally cannot sell. This is not a forecast; it is a property of the bytecode. The only question is detection quality. GoPlus honeypot detection is the industry-standard heuristic (simulate a buy-then-sell against a forked state); it has false-negatives (novel honeypot patterns) but very few false-positives → **fail-closed exclusion is correct.**
2. **`is_mintable == 1` (non-stablecoin) → unbounded dilution risk.** Stablecoins (USDT/USDC/USDD…) are mintable *by design* and are already excluded by Scout's `_STABLE_BASES` whitelist (`scout.py:26-29`); for the residual, a mintable alt is a standing rug vector. Lin & Tsyvinski (2021, NBER w26230) and Liu & Tsyvinski (2021, RFS) establish **vesting/inflation as a *priced, persistent negative factor*** — a mint authority is the unbounded form of the same effect.
3. **`slippage_modifiable == 1` / `personal_slippage_modifiable == 1` → de-facto honeypot-after-entry.** The owner can raise tax to 100% the moment enough retail is bagged. This is the documented mechanism behind the $TRUMP (Krause, SSRN 5104413, ~80% insider concentration, continuous bleed) and $LIBRA (Krause, SSRN 5149323, ~$100M extracted in hours) rug patterns (research/agents/17 §1.3).
4. **Holder concentration (top non-exchange holder > 50%) → mechanistic dump.** Luo, Ding, Xu (UCL/SSRN 5469066, 2025): meme-coin P&D is driven by **inventory concentration + attention fabrication**; the dump is mechanistic once insider exit begins. Luo et al. (ACM Web Conf 2026) document `dev`-wallet exit into copy-trader inflow — **copy-trade crowd is the exit liquidity.** A Scout that buys the post-pump volume spike *is* the copy-trade crowd.
5. **Thin / <24h pool → un-tradeable + rug-magnet.** A sub-$50k-liquidity pair cannot absorb the fleet's own exit; a brand-new pair is the signature of a launch-time rug. DexScreener `pairCreatedAt` and `liquidity.usd` make this a one-line filter.
6. **Unclaimed overhang → persistent pressure.** Tokenomist's own framing (§b.1) — a large Released/Circulating gap is standing selling pressure *independent* of the next cliff. This is the persistent complement to agent 22's time-bounded cliff events.

### b.3 The asymmetry — "avoid" is the alpha position

Across the cited lifecycle literature (research/agents/17 §1.4): **>90% of sub-$50M-FDV newly-listed tokens draw down >90% within 90 days; <5% "survive" to a Binance relist.** On a 5-slot portfolio (`ranker.py:22` `top_n=5`), the base-rate says ~1 of every 5 Scout picks is a candidate to die. A filter that removes the structurally-rug-prone 20–40% of the candidate pool is, by construction, **avoiding a known catastrophic drawdown source the current selector walks into blindly** (research/agents/06 §b — survivorship + listing-lookahead are *unresolved* in the repo; this filter is a partial mitigation). This is **risk-avoidance, not alpha generation** — but on a defensive-first fleet, avoiding one −80% name is worth multiple percent of fleet-level NAV per rebalance.

> **Caveat / honesty:** the contract signals detect *structural* rug vectors, not *behavioural* ones. A token with clean contract code (`is_mintable:0`, low tax, low concentration) can still pump-and-dump via coordinated social amplification (La Morgia 2023, Nghiem 2021 — research/agents/17 §1.1-1.2). This filter does **not** catch the "clean contract, fraudulent promotion" pattern; that is the job of the attention/social edge (research/agents/26, 39). The two are complementary: 46 = contract-cleanliness gate; 26/39 = behavioural-attention gate.

---

## (c) Free / cheap data sources

| Source | Endpoint | Cost | Coverage | Verified this session? |
|---|---|---|---|---|
| **GoPlus Security** | `api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={addr}` | **Free, no key** | 43 chains (ETH, BSC, Solana, Base, Arbitrum, Polygon, Tron, …) | ✅ live (USDT contract), ✅ supported_chains list |
| **DexScreener** | `api.dexscreener.com/latest/dex/search?q={SYMBOL}` ; `/tokens/v1/{chainId}/{addr}` | **Free, 60 req/min, no key** | All DEX pairs across chains | ✅ docs verified (`docs.dexscreener.com/api/reference`) |
| **Tokenomist** | `api.tokenomist.ai/v4/...` (free trial) | **Free trial**: 50 tokens, 1y back, 120 req/min | 1,500+ tokens, unlock calendars | (via research/agents/22 §c) |
| **DefiLlama** | `api.llama.fi/emissions` ; `/unlocks` | **Free, no key** | ~100 tokens (unlock fallback) | (via research/agents/22 §c) |
| **Etherscan / Solscan** | contract read (free tier) | Free (rate-limited) | Single-contract deep read | industry-standard |
| **CryptoRank** | `api.cryptorank.io/...` | Free tier; **key provisioned at `.env:62`, UNUSED** | Wide | (via research/agents/22 §c) |
| **RugCheck** (Solana) | `api.rugcheck.xyz/v1/tokens/{addr}/report` (community) | Free | Solana tokens | industry-standard; verify endpoint at integration |

**Recommended primary stack for Rapana:** **GoPlus (contract risk) + DexScreener (resolver + liquidity/age) + Tokenomist (supply/overhang, shared with agent 22).** All free, all off-exchange (they never touch MEXC's anti-bot detection — see §g). DefiLlama/CryptoRank as fallback. Total cost = $0 for a 50-symbol universe refreshed daily.

---

## (d) The `TokenomicsRiskFilter` — design

### d.1 Architecture principle — deterministic rules are load-bearing; LLM is advisory prose

Per research/agents/32: TradeTrap (`2512.02261`) proves LLM judgment is **fragile and adversarially manipulable** in the order path; AI-Trader (`2512.10971`) names **risk-control as the cross-market differentiator**, but the control must be schema-fenced. Therefore:

```
            ┌──────────────────────────────────────────────────────────────┐
            │  DETERMINISTIC RULES  (load-bearing — these decide)          │
            │  GoPlus + DexScreener + Tokenomist  →  risk_score + verdict  │
            │  verdict ∈ {HARD_EXCLUDE, CAP(x), PASS}                      │
            └─────────────────────┬────────────────────────────────────────┘
                                  │ (verdict is FINAL — LLM cannot change it)
                                  ▼
            ┌──────────────────────────────────────────────────────────────┐
            │  LLM ADVISORY SUMMARY  (fenced — prose only)                 │
            │  reads whitepaper/socials → {rationale: str,                 │
            │                               qualitative_flags: [str]}       │
            │  appended to record as llm_rationale. NEVER edits score/     │
            │  verdict. flags are advisory — cannot trigger exclusion       │
            │  alone (prevents hallucinated-rug false-excludes).           │
            └──────────────────────────────────────────────────────────────┘
```

The LLM is run **only on names that survive the deterministic HARD_EXCLUDE pass** (to avoid wasting calls on obvious rugs) and **cached per symbol for 24h** (tokenomics changes slowly). The output is a string + advisory flags; the portfolio manager / human reads it, the order path does not consume it.

### d.2 Signal spec — deterministic risk score (per symbol)

```python
# rapana/feeds/tokenomics.py  (new — mirrors feeds/feargreed.py)

@dataclass(frozen=True)
class TokenomicsRiskRecord:
    symbol: str
    # --- hard-exclude contract flags (each True = structural rug vector) ---
    honeypot: bool                  # is_honeypot==1 or cannot_buy==1
    mintable: bool                  # is_mintable==1   (stablecoins pre-excluded by Scout)
    hidden_owner: bool              # hidden_owner==1 or can_take_back_ownership==1
    closed_source: bool             # is_open_source==0   (can't audit → can't assess)
    slippage_modifiable: bool       # slippage_modifiable==1 or personal_slippage_modifiable==1
    pausable: bool                  # transfer_pausable==1
    blacklisted_fn: bool            # is_blacklisted==1 (selective-block function present)
    # --- tax / concentration (thresholded, cap-or-exclude) ---
    sell_tax: float                 # sell_tax in % (None if unresolvable)
    buy_tax: float
    top_holder_pct: float           # largest non-exchange, non-pool holder share in %
    top_holder_locked: bool         # is that top holder's stake locked?
    # --- supply / dilution (Tokenomist, shared with agent 22) ---
    unclaimed_overhang_pct: float   # (Released - Circulating)/Circulating in %
    next_cliff_pct_30d: float       # largest single cliff in next 30d, % circ supply (via agent 22)
    # --- liquidity / age (DexScreener) ---
    dex_liquidity_usd: float
    pool_age_hours: float           # now - pairCreatedAt
    # --- resolution ---
    resolved: bool                  # was a contract/pair found at all?
    is_native_coin: bool            # BTC/ETH/SOL — no contract, structurally low risk
    # --- output ---
    verdict: str                    # "HARD_EXCLUDE" | "CAP" | "PASS"
    cap_mult: float                 # 1.0 on PASS; in (0,1) on CAP; 0.0 on EXCLUDE
    risk_score: float               # 0..1 composite, for logging/ranking-penalty option
    rationale: str                  # deterministic one-line reason
    llm_rationale: str              # advisory prose (fenced LLM), "" if not run
    llm_flags: tuple[str, ...]      # advisory qualitative flags


def tokenomics_risk(symbol: str, now: pd.Timestamp) -> TokenomicsRiskRecord:
    """Resolve MEXC symbol -> (chain, contract) via DexScreener; pull GoPlus +
    Tokenomist; apply deterministic rules -> verdict. LLM summary run separately.
    Fail-soft: on any upstream error, return PASS with cap_mult=1.0 and a
    'data_unavailable' rationale (see §d.4 for the fail-mode debate)."""
```

### d.3 Hard-exclude rules (deterministic, ordered — first hit wins)

| # | Rule | Field(s) | Rationale |
|---|---|---|---|
| **E1** | `honeypot` OR `cannot_buy` | GoPlus `is_honeypot`, `cannot_buy` | Can enter, cannot exit. P(loss|entry)≈1. |
| **E2** | `closed_source` | GoPlus `is_open_source == 0` | Cannot audit any other flag → un-assessable. |
| **E3** | `mintable` AND NOT `is_native_coin` AND NOT stable | GoPlus `is_mintable == 1` | Unbounded dilution. (Stables already filtered by `_STABLE_BASES`.) |
| **E4** | `slippage_modifiable` OR `personal_slippage_modifiable` | GoPlus | Owner can raise tax post-entry → de-facto honeypot. |
| **E5** | `hidden_owner` OR `can_take_back_ownership` | GoPlus | Deployer can reclaim contract → re-mint/re-tax. |
| **E6** | `sell_tax > SELL_TAX_EXCLUDE` (default **25%**) OR `buy_tax > BUY_TAX_EXCLUDE` (default **25%**) | GoPlus | Tax so high it's effectively a slow rug. |
| **E7** | `dex_liquidity_usd < LIQ_FLOOR` (default **$50k**) | DexScreener | Un-tradeable; exit impossible; rug-magnet. |
| **E8** | `pool_age_hours < POOL_MIN_HOURS` (default **48h**) AND NOT `is_native_coin` | DexScreener `pairCreatedAt` | Brand-new pool = launch-time rug signature. (See research/agents/06 §b — fresh-listing negative drift.) |

**CAP rules** (verdict = `CAP`, `cap_mult < 1.0`) — marginal names, allow but shrink:

| # | Rule | `cap_mult` |
|---|---|---|
| **C1** | `sell_tax`/`buy_tax` in **(5%, 25%]** | 0.5 |
| **C2** | `top_holder_pct > 30` AND NOT `top_holder_locked` (and holder is not a known CEX/pool) | 0.5 |
| **C3** | `unclaimed_overhang_pct > 25` (Tokenomist Released ≫ Circulating) | 0.5 |
| **C4** | `next_cliff_pct_30d > 2` (shared with agent 22 — imminent dilution) | 0.5 |
| **C5** | `pool_age_hours` in **(48h, 14d]** | 0.7 |
| **C6** | `data_unavailable` (contract unresolvable, non-native) | 0.5 (conservative) |

`risk_score` (0..1, for the optional ranking-penalty integration mode, §f) = weighted normalisation of the non-binary flags, weighted toward the hard-exclude set. `cap_mult` multiplies the strategy's per-name max size (`RAPANA_RISK_MAX_POSITION_PCT=0.10`, per `.env`); HARD_EXCLUDE sets it to 0 (equivalent to Scout exclusion).

### d.4 Fail-mode — fail-closed on hard signals, fail-open on data-missing

The two failure modes are asymmetric and must be treated differently:

- **Hard signal present (E1–E8 true)** → **fail-closed: EXCLUDE.** These are contract bits; a false-positive costs one missed trade, a false-negative costs the position. The asymmetry favours exclusion.
- **Upstream API error / contract unresolvable** → two sub-cases:
  - **Native coin (BTC/ETH/SOL/…)** → **PASS** (no contract, structurally low rug risk; this is correct — majors should never be blocked by a tokenomics filter).
  - **Alt token that *should* have a contract but none found** → **CAP(0.5) + flag `data_unavailable`.** Conservative shrink, not full exclude — to avoid over-blocking the universe when DexScreener simply lacks the pair. (Tuneable: a stricter posture sets this to HARD_EXCLUDE; start permissive, tighten if backtest shows the excluded set had positive forward returns — i.e. let the `_run_arm` harness, research/agents/06 §d.3, arbitrate.)

---

## (e) Scout integration — minimal surface, PIT-safe

The integration mirrors agent 22's Option 1 (the cheapest, recommended-first path) exactly, because it is the same plumbing slot — an exclusion predicate on `Scout`.

### e.1 Inject an `exclude_fn` into `Scout`

Add an optional predicate to `Scout.__init__` (`scout.py:41-54`) and apply it inside `discover_candidates` after the existing stable/leveraged filters (`scout.py:66-68`):

```python
# scout.py:41-54  — add kwarg
def __init__(self, client, params=None, *, timeframe="1h", candidate_k=50,
             history_bars=None, exclude_fn=None):           # NEW
    ...
    self.exclude_fn = exclude_fn                            # NEW

# scout.py:66-68  — apply after the stable/leveraged filter
if base in _STABLE_BASES or _is_leveraged(base):
    continue
if self.exclude_fn is not None and self.exclude_fn(base):   # NEW
    continue
```

The caller owns a `TokenomicsRiskFilter` object that caches records (tokenomics changes slowly — **24h cache** is safe, vs F&G's 30min, `feargreed.py:25`). The pure `rank_universe` (`ranker.py:81`) is **untouched**, so the PIT backtest harness (`universe/validation.py:60-69`) stays valid — the filter is a caller-owned network touch, exactly like the `macro_fn` pattern (`agents/macro.py:23`).

### e.2 Size-cap path (for CAP names) — via `macro_fn` or a universe-level multiplier

The hard-excludes are handled by `exclude_fn` (Scout layer). The **size caps** need to reach the position sizer. Two clean options:

- **Option A (preferred, reuse existing slot):** inject the cap as a `macro_fn(symbol) -> (score, confidence)` into `MacroAnalyst` (`agents/macro.py:23`) — the slot already exists and emits `Signal`. A CAP'd name gets a bearish `score` proportional to `1 - cap_mult`, scaling its downstream size via the existing score→size mapping. Zero new plumbing.
- **Option B:** publish a `size_mult_fn(symbol) -> float` consumed by the portfolio manager alongside `RAPANA_RISK_MAX_POSITION_PCT`. Cleaner semantically (it's a risk multiplier, not a directional view) but requires a new seam.

Start with Option A; promote to B only if the macro-slot conflation causes issues.

### e.3 New feed + schema

`rapana/feeds/tokenomics.py` subclasses `Feed` (`feeds/base.py:6`), mirroring `feeds/feargreed.py` (cache + fail-soft, returning `(score, confidence)` for the macro-slot path). Persist the series for backtesting (mirrors agent 22's proposed `unlocks` table):

```sql
CREATE TABLE IF NOT EXISTS tokenomics_risk (
    symbol              TEXT NOT NULL,
    ts                  INTEGER NOT NULL,   -- snapshot epoch ms
    verdict             TEXT NOT NULL,      -- HARD_EXCLUDE|CAP|PASS
    risk_score          REAL NOT NULL,
    cap_mult            REAL NOT NULL,
    honeypot            INTEGER NOT NULL,   -- bool flags, 0/1
    mintable            INTEGER NOT NULL,
    slippage_modifiable INTEGER NOT NULL,
    sell_tax            REAL,
    top_holder_pct      REAL,
    unclaimed_overhang_pct REAL,
    dex_liquidity_usd   REAL,
    pool_age_hours      REAL,
    rationale           TEXT,
    PRIMARY KEY (symbol, ts)
);
```

(+ a slow-changing `token_contract(symbol, chain_id, address, first_seen_ts)` resolver table, so the DexScreener symbol→contract mapping is cached and PIT-reproducible.)

---

## (f) LLM role — fenced advisory summary (the "optional LLM summary")

This is the **one** place the LLM enters, and it is fenced exactly as research/agents/32 §(c) prescribes for the digest-prose / extraction roles.

**When:** only on symbols that **passed the deterministic HARD_EXCLUDE pass** (don't waste calls on confirmed rugs) AND are **about to be traded or held** (≤5 names/`ranker.py:22` + currently-held positions). Cached 24h per symbol. ~10 calls/day on the free tier.

**Inputs (read-only):**
- The deterministic `TokenomicsRiskRecord` (the LLM sees the numbers).
- Optional whitepaper/tokenomics doc text (fetched if a URL is resolvable from DexScreener `info.socials/websites`).

**Output (schema-bound — the LLM cannot return anything else):**
```json
{"rationale": "<≤2 sentence plain-English risk summary>",
 "qualitative_flags": ["anonymous_team" | "ponziomics_apy" | "copied_contract" | ...]}
```

**Hard fencing rules (enforced by the caller, not the LLM):**
1. `qualitative_flags` are **advisory only** — they are stored on the record and surfaced to the human, but **cannot trigger HARD_EXCLUDE or change `cap_mult` by themselves.** Only the deterministic rules (§d.3) decide. This prevents a hallucinated `"anonymous_team"` flag from excluding a legitimate token.
2. The LLM **never returns a numeric score, a verdict, or a size.** It returns strings only.
3. The LLM **never constructs a `TradeProposal`, `Signal`, or order.** It has no access to size, price, or the order path (TradeTrap `2512.02261` — judgment must stay out of execution).
4. On any LLM error/timeout, `llm_rationale=""`, `llm_flags=()`, verdict unchanged. Fail-soft.

**Why even bother with the LLM here?** Because the two genuinely-LLM-friendly risks (anonymous team, ponziomics-APY) are *not* contract-readable but *are* material, and the deterministic filter is blind to them. Surfacing them as advisory prose sharpens the load-bearing human-review loop (`RESEARCH-SYNTHESIS.md:79` — research/agents/32 §c4). It is the same value proposition as the digest-summary use: **translation/extraction, zero safety cost** because the output never touches a number that matters.

---

## (g) MEXC envelope compliance check

| Constraint | `TokenomicsRiskFilter` |
|---|---|
| Spot-only | ✓ (exclusion/cap filter — never opens a position) |
| Low-frequency | ✓ (daily refresh; tokenomics changes slowly; 24h cache) |
| No arbitrage | ✓ (no cross-venue/basis component) |
| No wash / no leverage | ✓ |
| **Off-exchange data** | ✓ — **GoPlus, DexScreener, Tokenomist are NOT MEXC endpoints.** The filter makes zero calls to MEXC, so it cannot trigger MEXC's anti-bot/anti-scanning detection (Risk Control Guideline §5.2.3, research/agents/16 §2.1). This is envelope-invisible. |
| Risk-gate compatible | ✓ (CAP names are shrunk within `RAPANA_RISK_MAX_POSITION_PCT=0.10`; excluded names never reach the gate) |

Fully envelope-clean. The filter is the *safest possible* MEXC-compatible edge: it is a read-only off-exchange data ingestion feeding a deterministic boolean. It has no behavioural footprint on MEXC whatsoever.

---

## (h) Recommended implementation order

1. **Build the resolver + GoPlus feed** (`feeds/tokenomics.py`): DexScreener `/latest/dex/search?q=<SYMBOL>` → `(chain_id, address, liquidity, pairCreatedAt)`, then GoPlus `token_security`. Implement E1–E8 hard-excludes. Cache 24h. **Verify the Solana GoPlus endpoint path** (`/sol-token-security`) at this stage — its exact query shape was not resolved this session; EVM path is confirmed. ~250 lines.
2. **Wire `exclude_fn` into `Scout`** (§e.1, 4-line change). Ship the hard-excludes first via Option 1 — pure drawdown-avoidance, very likely a free win.
3. **Add the Tokenomist overhang/cliff terms** (C3, C4) — **reuse agent 22's `UnlockFeed`** rather than re-fetching; the two agents share the same Tokenomist subscription. Persist to `tokenomics_risk` + `unlocks` tables.
4. **Backtest via the existing `_run_arm` harness** (`universe/validation.py:98-146`) comparing PIT-Scout vs PIT-Scout-minus-tokenomics-risk. **Critical:** the harness must apply the filter *point-in-time* — use each snapshot's as-of GoPlus/DexScreener state, never current-state-on-historical-names (that would be lookahead, since many rugs are *flagged only after* they rug). If historical per-snapshot risk data is unavailable, the honest backtest is *forward-only* (paper trade `RAPANA_ENV=paper`, `.env.example:8`) for ≥1 quarter before live capital.
5. **Add the CAP path** (C1–C6) via `macro_fn` injection (§e.2 Option A). Only after step 4 proves the hard-excludes don't hurt (i.e. the excluded set had negative forward returns).
6. **Add the fenced LLM advisory summary** (§f) last — zero safety cost, but also zero edge until the deterministic layer is validated. It's a human-loop sharpening tool, not a gating mechanism.
7. **Tune thresholds** (SELL_TAX_EXCLUDE, LIQ_FLOOR, POOL_MIN_HOURS, top-holder %) only through the `_run_arm` picker harness (research/agents/06 §d.3 — the cheapest research surface in the repo, under-used). Resist tuning by gut; every threshold is an overfit surface.

---

## Cited files
- `rapana/universe/scout.py:23,26-29,32-33,41-54,56-69` (Scout — `exclude_fn` injection point, mirrors agent 22 Option 1)
- `rapana/universe/ranker.py:20-26,81-107` (pure ranker — leave untouched for PIT safety; `top_n=5`)
- `rapana/feeds/base.py:6-20` (`Feed` ABC — template for `TokenomicsRiskFilter`)
- `rapana/feeds/feargreed.py:13-51` (cache + fail-soft pattern to mirror)
- `rapana/agents/macro.py:13-31` (already-plumbed `macro_fn` slot for the CAP path, §e.2 Option A)
- `rapana/data/store.py:13-43` (schema extension point for `tokenomics_risk` + `token_contract` tables)
- `rapana/universe/validation.py:60-69,98-146,202-210` (PIT backtest harness for filter comparison)
- `.env.example:61-62` / `.env:62` (dead `CRYPTORANK_API_KEY` — potential fallback source)
- Cross-refs: `research/agents/22` (unlocks — shared Tokenomist feed, overhang concept), `research/agents/06` (universe — edge #5 generalisation, `_run_arm` harness), `research/agents/17` (smallcaps — base-rate loss taxonomy), `research/agents/32` (LLM fencing — advisory-only mandate), `research/agents/16` (MEXC envelope — off-exchange data is detection-invisible), `research/agents/26,39` (behavioural-attention gates — complementary, not overlapping)

## External sources (verified ✅ this session unless noted)
- **GoPlus Security API (primary, free, no key):**
  - `https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={addr}` — ✅ live-verified (USDT contract returned full risk record: `is_mintable`, `is_honeypot`, `is_open_source`, `slippage_modifiable`, `transfer_pausable`, `holder_count`, top holders with `is_locked`)
  - `https://api.gopluslabs.io/api/v1/supported_chains` — ✅ 43 chains incl. Ethereum, BSC, Solana, Arbitrum, Polygon, Base, Tron, opBNB, zkSync, Linea, Optimism, Avalanche, Mantle, Scroll, Sonic, Berachain, World Chain, Monad
  - Docs: `https://docs.goplussecurity.io/` (field-semantics reference; docs site was intermittently unreachable this session — the live API is the source of truth)
- **DexScreener API (free, 60 req/min, no key):** `https://docs.dexscreener.com/api/reference` — ✅ verified; `/latest/dex/search`, `/tokens/v1/{chainId}/{tokenAddress}` return `liquidity.usd`, `fdv`, `marketCap`, `pairCreatedAt`, `txns`, `info.socials`
- **Tokenomist methodology:** `https://docs.tokenomist.ai/methodology/supply-metrics` — ✅ verified (Released vs Circulating = unclaimed overhang); API: `https://docs.tokenomist.ai/api-documents/introduction` (free trial: 50 tokens, 1y back, 120 req/min)
- **Academic / practitioner (rug & dilution predictability):**
  - La Morgia, Mei, Sassi, Stefa (ACM TOIT 2023) — pump-and-dump anatomy: `https://dl.acm.org/doi/abs/10.1145/3561300` (via research/agents/17)
  - Nghiem, Muric, Morstatter, Ferrara (ESWA 2021) — social+market joint P&D detection: `https://www.sciencedirect.com/science/article/pii/S0957417421007156` (via research/agents/17)
  - Luo, Ding, Xu (UCL/SSRN 5469066, 2025) — insider concentration + attention fabrication: `https://discovery.ucl.ac.uk/id_eprint/10220651/` (via research/agents/17)
  - Luo, Feng, Xu, Liu (ACM Web Conf 2026) — `dev`-wallet exit into copy-trader inflow: `https://dl.acm.org/doi/abs/10.1145/3774904.3792635` (via research/agents/17)
  - Krause, $TRUMP (SSRN 5104413): `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5104413` ; $LIBRA (SSRN 5149323): `https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5149323` (via research/agents/17)
  - Lin & Tsyvinski (2021, NBER w26230) & Liu & Tsyvinski (2021, RFS) — vesting/inflation as a priced persistent negative factor (via research/agents/22)
  - Bianchi (2020) — crypto listing/unlock drift (via research/agents/06, 22)
- **LLM-fencing mandate:** TradeTrap (`arXiv:2512.02261`), AI-Trader (`arXiv:2512.10971`), LiveTradeBench (`arXiv:2511.03628`) — via research/agents/32 §(b)
- **Resolver/contract-read fallbacks:** Etherscan, Solscan (free tier, single-contract read); RugCheck (Solana, community — verify endpoint at integration); DefiLlama `https://api.llama.fi/emissions` (unlock fallback, no key)

---

## (i) One-line bottom line

A deterministic `TokenomicsRiskFilter` reading **free GoPlus contract-risk bits + DexScreener liquidity/age + Tokenomist overhang** hard-excludes the structurally-rug-prone 20–40% of the Scout candidate pool (honeypot, mintable, modifiable-tax, thin/new pool, hidden owner) and caps the marginal ones — a defensive edge that costs $0, is MEXC-envelope-invisible (off-exchange data, zero behavioural footprint), and fences the LLM to an advisory-prose role that can never trigger an exclusion (TradeTrap/AI-Trader mandate), directly plugging into Scout via the same `exclude_fn` slot agent 22 already scoped.
