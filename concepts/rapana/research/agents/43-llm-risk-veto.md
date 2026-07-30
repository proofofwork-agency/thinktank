# 43 — LLM as a RISK VETO / sanity gate (`NewsVetoChecker`)

**Agent:** 43/60 · **Scope:** `rapana/risk/guardrails.py` (integration point `:194`), `rapana/fleet/orchestrator.py`, `rapana/config.py`, `rapana/journal/ledger.py`, `rapana/agents/auditor.py`, `rapana/agents/brain.py`
**Goal:** Design the one LLM role the evidence unanimously endorses — a **schema-fenced boolean veto** consulted inside `PreTradeChecker.check()`. The LLM can *only* deny a trade the deterministic gate already approved; it can never construct, resize, or greenlight a `TradeProposal`. A wrong call costs one missed trade; a harmful trade from the LLM is structurally impossible. This is agents 5/32's top-ranked non-predictive use (`05-fleet-llm-edge.md:110-114`, `32-llm-papers.md:48-56,96`).

All repo citations are `file:line`.

---

## (a) Why veto is the cleanest LLM seat — and where it plugs in

The repo's own architecture makes this design near-mandatory. `PreTradeChecker.check()` (`risk/guardrails.py:189-233`) is already a chain of independent deny-gates: kill-switch → circuit-breaker → rate-limiter → notional cap → sanity band → exposure caps. Each gate returns `self._deny(reason)` (`guardrails.py:235-239`), which writes a `risk_veto` row to the hash-chained ledger (`guardrails.py:238`, `ledger.py:111-132`) and returns `RiskDecision(approved=False, reason=...)` (`guardrails.py:59-62`). A `NewsVetoChecker` is simply one more sibling in that chain. It adds **no new control-flow primitive, no new audit primitive, no new failure surface** — it reuses the exact `_deny` path the kill switch and circuit breaker already use.

**Insertion point:** between the rate-limiter check (`guardrails.py:194-197`) and the notional cap (`guardrails.py:199-204`). Placing the veto *after* the system-safety gates (kill/breaker/rate) means a news veto never fires on a cycle that was going to be denied anyway — no wasted LLM call. Placing it *before* the per-order economics (notional/sanity/exposure) means a news veto short-circuits the rest of the chain. Both agents 5 and 32 independently nominated this exact seam (`05-fleet-llm-edge.md:114`, `32-llm-papers.md:54`).

**Load-bearing property — the asymmetry of the error:** a *false veto* skips one trade (opportunity cost, bounded by `max_position_pct=0.10`, `config.py:57`); a *false approval* is unachievable because the LLM's output vocabulary is `{veto: bool, reason: str}` and the deterministic gate has *already* approved before the LLM is even consulted. The LLM never sees size, price, or side-derived logic (`TradeProposal` is constructed only by `PortfolioManager.decide`, `orchestrator.py:226-229`); the veto checker receives only `{symbol, side}` — the minimum needed to apply side-conditional rules (§c).

---

## (b) The veto decision — inputs, rules, schema

### Inputs (what the LLM is shown)

The checker assembles a **bounded, read-only context packet** per proposal. Critically, the packet contains **no sizing or price information** — only identity + regime/news signals — so the model cannot implicitly "approve" a larger trade by reasoning about notional.

```python
@dataclass(frozen=True)
class NewsVetoContext:
    symbol: str                 # e.g. "FET/USDT"
    side: str                   # "buy" | "sell"  (only side-conditional rules need it)
    # Symbol-level signals (deterministic, pre-computed; LLM does NOT call APIs):
    token_events: list[dict]    # [{type, ts, magnitude}]  unlocks/delistings/airdrops
    funding_state: dict | None  # {rate, percentile, crowd} if available
    # Macro/contagion signals:
    stablecoin_health: dict | None  # {depeg_bps, symbol} e.g. {"depeg_bps": 180, "symbol": "USDC"}
    contagion_alerts: list[dict]    # [{venue, event, affected_symbols}] hacks/bridge exploits
    regulatory_flags: list[str]     # ["SEC_action_XYZ", ...]
    fear_greed: int | None          # 0..100 if available
    as_of_ts: int               # packet build time (stale packets are skipped, not vetoed)
```

Every field is **pre-fetched by deterministic code** (calendar scrapers, funding pollers, a depeg monitor). The LLM is a *consumer* of this packet, never the fetcher. This mirrors the existing `sentiment_fn` / `macro_fn` injection pattern (`agents/sentiment.py:23`, `agents/macro.py`) where external data arrives as a function, not as live model tool-use. If any field is missing/stale, the conservative default is **no veto** (§d).

### When to veto (the rule catalogue)

The veto logic is a small, enumerated, **side-conditional** rule set. The LLM's job is to *recognize which rule applies* from the context packet — a classification task, not a forecast (`32-llm-papers.md:48-51`).

| Rule ID | Trigger (from packet) | Side | Vetoes | Rationale (links to repo research) |
|---|---|---|---|---|
| `unlock_imminent` | token unlock ≥0.5% supply in <48h | buy | ✅ | Dump risk; `22-token-unlocks.md` |
| `delisting_window` | MEXC delisting announced, trading-in-close window | buy & sell-to-open | ✅ | Liquidity trap; `11-mexc-delistings.md` |
| `hack_contagion_active` | bridge/exploit affecting symbol or its L1 | buy | ✅ | Contagion drawdown; `RESEARCH-SYNTHESIS.md` tail risk |
| `depeg_stress` | major stable depeg >150bps | buy | ✅ | Portfolio-wide de-risk; `21-stablecoin-depeg.md` |
| `funding_extreme_crowded_long` | funding percentile >95 *and* side=buy | buy | ✅ | Squeeze risk on crowded long; `12-mexc-funding.md`, `29-funding-crossvenue.md` |
| `fg_euphoria_new_long` | Fear&Greed >85 *and* opening new long | buy (open) | ✅ | Top-of-cycle new entry; `26-social-sentiment.md` |
| `regulatory_action` | named regulatory action on symbol/issuer | buy | ✅ | Gap-down risk |

**Two structural constraints on the table:**

1. **Vetoes skew toward the buy side / new-long entries.** A veto on a *sell* is only warranted in the delisting-window case (where even exiting can trap you in a halted book). This bias is intentional: the catastrophic trades the benchmarks document (70%+ drawdowns, `32-llm-papers.md:14`) are *entries into falling knives*, not risk-reducing sells. Vetoing a legitimate sell-to-flatten would be a net negative.
2. **Sells that reduce exposure are never vetoed.** `PreTradeChecker` only enforces exposure caps on `side=="buy"` (`guardrails.py:217-231`); a sell-to-close is the fleet's natural de-risking path. A news veto that blocked a sell would be actively harmful. The checker's `side` parameter exists precisely to express this asymmetry.

### Output schema (the ONLY thing the LLM may emit)

```json
{
  "veto": true,
  "rule_id": "unlock_imminent",
  "reason": "FET unlock 1.2% supply in 18h; entry vetoed",
  "confidence": 0.8
}
```

- **`veto`** (bool): the only field that affects control flow. Default `false`.
- **`rule_id`** (enum): must be one of the table's IDs; anything else → schema fail → no veto.
- **`reason`** (str ≤200 chars): human-readable, journaled, never parsed for logic.
- **`confidence`** (float 0..1): advisory-only; does not affect whether the veto fires (it either does or doesn't), but is logged for the calibration loop (§e).

The schema is validated **defensively and fail-soft**, mirroring `OpenAICompatibleBrain.reason` (`brain.py:92-95`): any JSON error, missing field, unrecognized `rule_id`, or timeout → treat as `{veto: false, reason: "schema_error_no_veto"}` and log. An LLM hallucination can never produce a veto it isn't entitled to, because the `rule_id` enum is enforced *after* the model speaks.

---

## (c) Integration sketch — minimal, additive, no new primitive

The change is deliberately small. A new optional collaborator on `PreTradeChecker`, consulted at one line.

### 1. The checker dataclass (new, in `risk/guardrails.py`)

```python
@dataclass
class NewsVetoDecision:
    veto: bool
    rule_id: str | None
    reason: str


class NewsVetoChecker:
    """LLM-backed adverse-news veto gate. Advisory by default; promotable to hard.

    Consulted inside PreTradeChecker.check() AFTER the deterministic system gates
    (kill/breaker/rate) approve. The LLM may ONLY veto; it can never approve a
    trade the deterministic chain rejected, and it never sees size/price.
    Fail-soft: any schema/timeout error => no veto (conservative = trade proceeds).
    """

    def __init__(
        self,
        brain: "Brain | None" = None,                 # from rapana.agents.brain
        context_fn: Callable[[str, str], NewsVetoContext] | None = None,
        mode: str = "advisory",                        # "advisory" | "hard"
        timeout: int = 8,
    ) -> None: ...

    def check(self, symbol: str, side: str) -> NewsVetoDecision: ...
```

### 2. The single insertion point in `PreTradeChecker.check()`

```python
    def check(self, proposal: TradeProposal) -> RiskDecision:
        if self.kill_switch.is_tripped():
            return self._deny("kill_switch_tripped")                 # guardrails.py:190
        if self.breaker.is_tripped():
            return self._deny("circuit_breaker_tripped")             # guardrails.py:192
        if self.rate_limiter is not None and self.rate_limiter.would_exceed():  # :194
            return self._deny(f"order rate would exceed {self.policy.max_orders_per_min}/min")

        # === NEW: LLM news/regime veto (advisory -> hard after calibration) ===
        if self.news_veto is not None and self.news_veto.mode == "hard":
            vd = self.news_veto.check(proposal.symbol, proposal.side)
            if vd.veto:
                return self._deny(f"llm_news_veto:{vd.rule_id}: {vd.reason}")

        # Per-order notional cap.                                  # guardrails.py:199
        if proposal.notional > self.policy.max_notional_per_order:
            ...
```

`PreTradeChecker.__init__` gains one optional field, `news_veto: NewsVetoChecker | None = None` (`guardrails.py:169-187`), threaded from `orchestrator.py:238-247` exactly like `rate_limiter` and `ledger` already are. **Default `None`** keeps the fleet fully deterministic when the LLM is off (`llm_provider="none"`, `config.py:65`) — the existing test suite (`tests/test_risk.py`) passes unchanged.

### 3. Audit trail — reuse, don't add

A hard veto flows through the existing `self._deny(...)` (`guardrails.py:235-239`), which already appends a `risk_veto` row to the hash-chained ledger (`ledger.py:111-132`) and surfaces in `ComplianceAuditor.digest()` under `risk vetoes` (`auditor.py:29,36,40-41`). The only addition is a richer `reason` string (`llm_news_veto:unlock_imminent: ...`) — no new ledger `kind`, no new digest branch. In **advisory mode** the veto is *not* applied to the decision; instead the `NewsVetoDecision` is journaled as a separate `news_veto_advisory` row so the calibration loop (§e) can score it without affecting fills. This is the one new `kind` string, and it reuses `DecisionLedger.append` unchanged.

---

## (d) Anti-bias guarantees — why the LLM cannot hurt you

The design enforces five invariants, four inherited from the existing architecture (`05-fleet-llm-edge.md:183-190`) and one new:

1. **One-directional gate.** The LLM is consulted *only* on the `approved` branch of an already-passed deterministic check. There is no code path where a model output changes `approved=False` to `True`. The combiner (`signals.py:87-104`) and `PortfolioManager.decide` are untouched. **The LLM can only subtract consent, never add it.**
2. **Schema-fenced output.** The model's effective action space is `{veto ∈ {true, false}} × {rule_id ∈ enum}`. Unknown `rule_id`, malformed JSON, or timeout all collapse to `veto=false` (fail-open-to-trade). This is the inverse of TradeTrap's finding that unconstrained LLM judgment is adversarially manipulable (`32-llm-papers.md:16,34`): here the attack surface is a single boolean the model can only set in one direction.
3. **No size/price leakage.** `NewsVetoContext` deliberately omits `qty`, `price`, `notional`, `reference_price`. The checker signature is `check(symbol, side)`. The model cannot implicitly "approve a bigger trade" because it never learns there is one.
4. **Sells are protected.** The rule catalogue vetoes overwhelmingly on `buy`/new-long; a sell-to-flatten is the fleet's de-risk path (`guardrails.py:217` only caps buys). Blocking a sell in a crisis would be the one genuinely dangerous LLM action, so the rules forbid it by construction.
5. **Default-off.** `news_veto=None` is the default; `mode` starts at `"advisory"`; `llm_provider="none"` (`config.py:65`) never constructs a brain at all (`brain.py:114-115`). Promotion to `mode="hard"` is a deliberate, validated config change (§e), gated on observed precision.

**Conservative default under uncertainty:** every ambiguous state resolves to *no veto* (trade proceeds). Stale context packet → no veto. Missing field → no veto. Low model confidence → no veto (veto requires the model to *positively* claim a rule applies). This is the correct asymmetry: the deterministic edge is assumed to exist (it passed all hard gates), so the prior is "trade is fine unless the LLM has a *specific, named* reason it isn't."

---

## (e) Calibration plan — advisory → hard veto, precision over recall

A veto that fires too often is a slow bleed of missed edge; a veto that never fires is dead weight. The promotion path makes this measurable before any capital depends on it.

### Metrics tracked (advisory mode, journaled as `news_veto_advisory`)

For each advisory veto, record `{symbol, side, rule_id, reason, confidence, as_of_ts}` and the *counterfactual outcome*: the PnL the trade *would have realized* over the same horizon the reflection loop uses (`memory.py:53` default 24h). Then:

- **Veto precision** = P(vetoed trade would have *lost*) = count(vetoed ∧ outcome<0) / count(vetoed). This is the metric that matters for *justifying* a hard veto — a veto is "correct" iff it stopped a loser.
- **Veto recall** = P(actual loser was vetoed) = count(vetoed ∧ outcome<0) / count(all losers). Lower recall is tolerable (the deterministic gates already catch most losers); low precision is not.
- **Opportunity cost** = Σ outcome of vetoed trades that *would have won*. This bounds the damage of false vetoes once promoted to hard.

### Promotion gates (advisory → hard)

A `rule_id` (or the whole checker) is promoted to `mode="hard"` only when, over a minimum sample of **N≥30 advisory vetoes** of that rule:

1. **Precision ≥ 0.60** — at least 60% of vetoed trades would have lost. (Above the ~50% base rate of random entry; conservative.)
2. **Net protective value > 0** — `Σ|losses_avoided| > Σ|gains_missed|`, i.e. the veto is net-positive even after opportunity cost.
3. **No single rule dominates false vetoes** — if one `rule_id` (e.g. `fg_euphoria_new_long`) has precision <0.50, it stays advisory even if the aggregate passes; promote *per-rule* to isolate good rules from noisy ones.

Promotion is a config flip (`RAPANA_NEWS_VETO_MODE=hard`) plus a minimum-sample check enforced in code, not a model judgment. **Demotion** is symmetric: if a promoted rule's rolling precision (last 30 vetoes) drops below 0.50, it auto-reverts to advisory and logs a `news_veto_demoted` row. This mirrors the autopilot promote/demote hysteresis already in `config.py:49-54` (`autopilot_promote_sharpe`, `autopilot_demote_drawdown`) — same philosophy, applied to a veto gate instead of capital scaling.

### Phasing

| Phase | `mode` | What ships | What's measured | Capital at risk from LLM |
|---|---|---|---|---|
| **0 — off** | n/a (`news_veto=None`) | Deterministic fleet, unchanged | nothing | zero |
| **1 — shadow** | `advisory` | Checker runs, journals `news_veto_advisory`, **never denies** | precision/recall/opportunity-cost accumulation | zero |
| **2 — selective hard** | `hard` (per-rule) | Highest-precision rule(s) deny; rest stay advisory | live veto precision vs shadow baseline | bounded to opportunity cost of one `max_position_pct` trade |
| **3 — full hard** | `hard` (all qualifying rules) | Every rule meeting gates denies | rolling precision, auto-demotion | bounded (same as above) |

Phase 1 is the only safe starting point and can ship immediately: it is a pure observability addition with zero order-path effect, exactly like the existing advisory Bull/Bear debate (`portfolio_manager.py:46-51`). The reflection loop's existing time-ordered resolve mechanism (`memory.py:80-108`) can be reused to compute counterfactual outcomes without new infrastructure.

---

## (f) Settings additions (mirrors the LLM block at `config.py:64-68`)

```python
# --- News/regime veto (LLM risk gate; advisory by default) ---
news_veto_enabled: bool = Field(default=False, alias="RAPANA_NEWS_VETO_ENABLED")
news_veto_mode: str = Field(default="advisory", alias="RAPANA_NEWS_VETO_MODE")  # advisory|hard
news_veto_timeout: int = Field(default=8, alias="RAPANA_NEWS_VETO_TIMEOUT")
news_veto_min_sample_promote: int = Field(default=30, alias="RAPANA_NEWS_VETO_MIN_SAMPLE")
news_veto_promote_precision: float = Field(default=0.60, alias="RAPANA_NEWS_VETO_PROMOTE_PRECISION")
news_veto_demote_precision: float = Field(default=0.50, alias="RAPANA_NEWS_VETO_DEMOTE_PRECISION")
```

A `@field_validator("news_veto_mode")` coerces unknown values to `"advisory"` (mirroring `llm_provider` coercion at `config.py:88-94`), so a typo can never silently arm a hard veto.

---

## (g) Honest calibration / summary

**Is:** a schema-fenced, advisory-by-default, one-directional veto gate that reuses `PreTradeChecker`'s existing `_deny` path and ledger, plugs in at exactly the seam agents 5/32 nominated (`guardrails.py:194`), and inherits the codebase's "LLM fenced outside the order path" invariant (`RESEARCH-SYNTHESIS.md:65`). Promotion to a capital-affecting hard veto is gated on measured precision ≥0.60 over ≥30 advisory samples, with auto-demotion.

**Is not:** a forecast, an alpha source, or a seat from which the LLM can approve or resize a trade. The model's action space is a single boolean it can only set toward *caution*. The deterministic edge — and all sizing — remains untouched.

**Calibration notes:** (i) The rule catalogue in §b is a design proposal, not a backtested edge; the 0.5% unlock / 150bps depeg / 95th-percentile funding thresholds are reasoned defaults that should be tuned against shadow-mode veto precision before any promotion. (ii) Precision ≥0.60 is conservative relative to a ~50% random-entry base rate but is still a judgment call; it mirrors the spirit of `autopilot_promote_sharpe=1.0` (`config.py:50`) rather than being derived from data. (iii) The 24h counterfactual horizon inherits the reflection loop's known weakness (`05-fleet-llm-edge.md:82-86`) that sign-of-return is a noisy scoring task; veto precision should ideally be re-scored against risk-adjusted PnL once that loop is upgraded. (iv) No new tests are written here; the design is additive and the existing `tests/test_risk.py` suite passes unchanged because `news_veto` defaults to `None`.
