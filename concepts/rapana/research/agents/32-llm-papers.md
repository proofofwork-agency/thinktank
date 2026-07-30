# 32 — LLM/agent crypto-trading papers (2023–2026): what's left once price-PREDICTION is off the table

**Agent:** 32/60 · **Scope:** the literature on LLM/agent trading systems and, downstream, `rapana/risk/guardrails.py`, `rapana/fleet/orchestrator.py`, `rapana/fleet/memory.py`, `rapana/agents/auditor.py`, `rapana/universe/scout.py`, `rapana/agents/sentiment.py`
**Goal:** The repo's docs are explicit that LLM price-*prediction* has no OOS edge (`RESEARCH-SYNTHESIS.md:11,39`). This note surveys the 7 named papers + the cross-model benchmarks and isolates the **non-predictive** uses the evidence actually supports, then maps each to a concrete rapana plug-in point (`file:line`).

All repo citations are `file:line`. All paper citations are arXiv `id` + URL (every abstract fetched live this session, ✅). The two honest base facts I build on: **best LLM ~6% over 50 days, peers 70%+ drawdowns** (LiveTradeBench, `2511.03628`) and **925k wallets net −$191.7M** (`RESEARCH-SYNTHESIS.md:11,114`).

---

## (a) What the literature actually says — the predictive edge is dead OOS

Three of the seven papers are **live, contamination-controlled benchmarks** (not backtests), and all three reach the same conclusion from different angles:

- **LiveTradeBench (`2511.03628`, 50-day live, 21 LLMs, US stocks + Polymarket):** *"high LMArena scores do not imply superior trading outcomes."* Best model ~6% over 50 days, others 70%+ drawdowns; authors explicitly decline to claim reliable alpha. ✅
- **AI-Trader (`2512.10971`, live, data-uncontaminated, US + A-shares + crypto, 6 LLMs):** *"general intelligence does not automatically translate to effective trading capability, with most agents exhibiting poor returns and weak risk management."* The load-bearing finding: **"risk control capability determines cross-market robustness."** ✅
- **TradeTrap (`2512.02261`, adversarial stress-test of LLM trading agents):** *"small perturbations at a single component can propagate … and induce extreme concentration, runaway exposure, and large portfolio drawdowns"* — i.e. LLM judgment is **fragile and adversarially manipulable** in the order path. ✅

The other four papers (TradingAgents, FinGPT, FinAgent, FinRobot) are **system/platform papers** whose returns claims are **backtested**, not live, and the repo already treats backtest→live decay (30–80%) as the rule (`RESEARCH-SYNTHESIS.md:38`). So their headline return numbers do **not** survive the OOS/live test that the three benchmarks apply.

**Therefore** — once prediction is excluded, what the literature *does* show works (or at least survives) is uniformly on the **classification / veto / extraction / reporting** axis, never the "what will the price do" axis. The rest of this note catalogues exactly that.

---

## (b) Paper classification table — claimed edge vs OOS verdict

| Paper (arXiv, ✅ fetched) | Year | System type | Claimed edge (per abstract) | OOS / live verdict | Viable LLM use that survives |
|---|---|---|---|---|---|
| **TradingAgents** `2412.20138` ✅ [arxiv.org/abs/2412.20138](https://arxiv.org/abs/2412.20138) | 2024–25 | Multi-agent firm sim: fundamental/sentiment/TA analysts + **Bull/Bear debate** + risk-mgmt team + traders | "superiority over baselines in cumulative returns, Sharpe, max drawdown" — **backtested** on stock tick data | **Returns don't transfer OOS** (in-sample only; no live crypto eval). The durable contribution is the **multi-role debate scaffold + risk-management-team veto structure**, not the directional calls. | **Risk-team veto layer** + the debate scaffold rapana already has (`researchers.py`) |
| **FinGPT** `2306.06031` ✅ [arxiv.org/abs/2306.06031](https://arxiv.org/abs/2306.06031) | 2023 | Open-source FinLLM; data-centric, LoRA, **data-curation pipeline** | "robo-advising, algorithmic trading, low-code" — **infrastructure**, no returns claim | Not a returns benchmark; its value is **infrastructure** (curation + lightweight adaptation) feeding downstream classification/extraction, not raw prediction. | **Data-curation + structured-extraction toolkit**; robo-advising = report gen |
| **FinAgent** `2402.18485` ✅ [arxiv.org/abs/2402.18485](https://arxiv.org/abs/2402.18485) | 2024 | Multimodal agent: news+price+Kline, **tool-augmented**, dual-level reflection, diversified memory retrieval; tested on stocks **and crypto** | "+36% avg profit over 9 baselines; 92.27% return on one dataset" — **backtested** | **Returns decay OOS** (backtest-only; repo's 30–80% decay applies). The durable idea is the **multimodal news/chart fusion + reflection memory**, which aligns with rapana's `ReflectionMemory`. | **Multimodal event/news → structured signal**; reflection-memory concept |
| **FinRobot** `2405.14767` ✅ [arxiv.org/abs/2405.14767](https://arxiv.org/abs/2405.14767) | 2024 | Open-source agent platform; **Financial Chain-of-Thought**, multi-source LLMs | "democratize financial analysis" — **platform whitepaper**, no returns claim | Not a returns benchmark; value is the **CoT analysis-structuring + toolchain** for reporting/classification, not alpha. | **CoT-structured analysis + report generation** layer |
| **LiveTradeBench** `2511.03628` ✅ [arxiv.org/abs/2511.03628](https://arxiv.org/abs/2511.03628) | 2025 | **LIVE** 50-day, 21 LLMs, US stocks + Polymarket | "seeking real-world alpha" — authors **decline to claim reliable alpha** | **Prediction fails OOS** (best ~6%, peers 70%+ DD). Durable finding: models show **distinct portfolio "styles"** → usable as **regime/risk-profile labels**, not predictors. | **Regime / risk-style classification** (orthogonal to direction) |
| **AI-Trader** `2512.10971` ✅ [arxiv.org/abs/2512.10971](https://arxiv.org/abs/2512.10971) | 2025 | **LIVE**, data-uncontaminated, US + A-shares + **crypto**, 6 LLMs | "general intelligence ≠ trading capability; most agents poor returns + weak risk mgmt" | **Prediction fails OOS.** Durable finding: **"risk control capability determines cross-market robustness"** and excess returns are easiest in **liquid** markets (crypto majors). | **Risk/veto layer** is the differentiator — direct support for LLM-as-gatekeeper |
| **TradeTrap** `2512.02261` ✅ [arxiv.org/abs/2512.02261](https://arxiv.org/abs/2512.02261) | 2025 | Adversarial stress-test of LLM trading agents (4 components) | "small perturbations → extreme concentration, runaway exposure, large drawdowns" | **LLM judgment is fragile/manipulable** in the order path. Strongest evidence that the LLM must be **schema-fenced OUT of execution**. | **Schema-constrained veto/classifier only** — never order routing |

### Reading the table

1. **Price-prediction edge: universally fails or is untested OOS.** Of the 7, only the 3 live benchmarks test OOS — and all 3 reject predictive alpha. The 4 system papers report backtested numbers that the repo already assumes decay.
2. **The edges that survive are non-predictive:** *risk-team veto* (TradingAgents, AI-Trader), *regime/style classification* (LiveTradeBench), *multimodal event extraction* (FinAgent), *data curation + report generation* (FinGPT, FinRobot), and *schema fencing* (TradeTrap).
3. **Crypto specifically:** AI-Trader notes excess returns are *easiest in highly liquid markets* — i.e. MEXC's BTC/ETH majors, **not** the long-tail small-caps. That caps where any LLM-adjacent edge is even plausible.

---

## (c) The viable non-predictive uses → concrete rapana plug-in points

Each use below is **veto / classification / transcription / translation** — never "predict price." Each maps to an existing seam in the codebase (already audited in `05-fleet-llm-edge.md:100-134`); this note adds the literature justification and pins the exact `file:line`.

### (c1) News / adverse-event VETO — *the cleanest, highest-evidence use*

**What it is:** read a news/feed, decide *"is there a material adverse event for this symbol right now"*, emit a hard boolean veto. A gate, not a forecast.

**Literature support:** AI-Trader — *"risk control capability determines cross-market robustness"* (`2512.10971`); TradeTrap — the entire paper is evidence that LLM judgment *must* be fenced out of the order path and confined to a schema-bound veto (`2512.02261`). This is exactly `RESEARCH-SYNTHESIS.md:65`'s "news vetoes" in-scope item.

**Plug-in point:** add a `NewsVetoChecker` as a sibling of `CircuitBreaker`/`KillSwitch`, consulted inside `PreTradeChecker.check()` **between the rate-limiter and the notional check** — `rapana/risk/guardrails.py:194-197`. A veto returns `self._deny("llm_news_veto: <reason>")` via the existing `_deny` path (`guardrails.py:235-239`), so it inherits the same audit trail and ledger entry. **The LLM returns `{veto: bool, reason: str}` only — it never constructs a `TradeProposal` (`guardrails.py:41-56`) and never sees size.** A wrong veto misses a trade (opportunity cost); a wrong "buy" is structurally impossible.

**Expected value:** avoids catastrophic bad trades (delistings, hack news, unlock dumps) — the *one* class where LLM language understanding beats deterministic rules. Directly addresses the 70%+ drawdowns the benchmarks record when no veto exists.

### (c2) Regime / market-style CLASSIFICATION — *not price direction*

**What it is:** label the market `{trending | range | risk-off | breakout-benign}` for a symbol. This is a **labelling** task (LiveTradeBench: models show *"distinct portfolio styles reflecting risk appetite"*) — orthogonal to "will BTC go up."

**Literature support:** LiveTradeBench's "distinct portfolio styles" (`2511.03628`) ⇒ regime/risk-appetite labels are learnable; AI-Trader's cross-market-robustness finding (`2512.10971`) ⇒ the *environment type*, not the direction, is what agents can read.

**Plug-in point:** add `RegimeClassifier.label(symbol, provider)` returning a fixed enum, wired at **the top of `_process_symbol` — `rapana/fleet/orchestrator.py:189`**, *before* analysts run (`orchestrator.py:199`). The label feeds (i) the injectable strategy set in `MarketAnalyst` (`agents/market.py:27,31`) and (ii) the **regime-conditional** `ReflectionMemory.weight(source, regime)` upgrade that agent-05 identifies as the single change that converts the reflection loop from curve-fit to real edge (`05-fleet-llm-edge.md:92,96`; today `weight()` is unconditional at `fleet/memory.py:114-121`). The LLM never touches `signals`, `weighted_combine` (`signals.py:87-104`), or the proposal.

**Expected value:** calibration — it makes the existing adaptive-weighting loop *conditional* ("macro feed is signal in regime X, noise in regime Y") instead of marginal. This is the highest-upside non-predictive use *in theory*, but also the highest implementation risk (see ranking in §d — deferred to Phase-2).

### (c3) Unstructured → structured extraction (listings, unlocks, calendars) — *transcription, not prediction*

**What it is:** translate "MEXC lists X/USDT at 14:00 UTC" or "1.2% of FET supply unlocks Friday" into a structured record. This is the **one** use where MEXC's venue (listing-heavy, unlock-heavy) creates a blind spot the deterministic analysts cannot see (`agents/sentiment.py:26-30` is a stub; `agents/macro.py` is `fn`-injected).

**Literature support:** FinAgent's multimodal news/chart fusion (`2402.18485`); FinGPT's data-curation pipeline (`2306.06031`); FinRobot's CoT toolchain (`2405.14767`). All three are, at base, *extraction/structuring* contributions.

**Plug-in points (two distinct, both veto-shaped):**
- **Universe blacklist (safer).** Inject an LLM-extracted *blacklist* into `Scout.discover_candidates()` at `rapana/universe/scout.py:56-69` — e.g. "skip symbols with a scheduled unlock <48h." This sits **upstream** of `_maybe_rebalance_universe` (`orchestrator.py:153-180`) and prevents the fleet from ever picking up the bad name. Veto-only.
- **Event analyst (mild alpha-extension).** Build `LLMEventAnalyst(Analyst)` emitting `Signal(source="event", confidence≤cap)`, injected into the analyst list at `rapana/fleet/orchestrator.py:91-95`. A hallucinated bullish event is bounded by `max_weight=0.10` (`orchestrator.py:51`) and the risk gate, so it can only slightly over-allocate one small position.

**Expected value:** covers the analysts' blind spots on MEXC's listing/unlock calendar (the repo has dedicated research notes `10-mexc-listings.md`, `22-token-unlocks.md`, `15-mexc-listing-detection.md` — all currently unstructured inputs). The **blacklist** variant is strictly safer than the **analyst** variant and should ship first.

### (c4) Post-hoc digest / report generation — *zero safety cost*

**What it is:** summarize the day's fills/vetoes/source-weight changes into a human-readable brief, *after* the deterministic digest is built.

**Literature support:** FinGPT "robo-advising" (`2306.06031`); FinRobot "Financial CoT" analysis/reporting (`2405.14767`). Both are, at root, *report-generation* platforms — and that is the part that demonstrably works.

**Plug-in point:** an LLM summarizer operating on the output of `ComplianceAuditor.digest()` at `rapana/agents/auditor.py:27-55`, producing a parallel `digest_prose` field. It **never edits the ledger** (the hash-chained ledger at `auditor.py:23-25` is read-only input). The reflection loop's opaque `analytics()` dump (`fleet/memory.py:126-127`) can likewise be rendered into prose ("macro feed lost influence this week: accuracy 0.41") — pure translation.

**Expected value:** directly improves the *"human reviews daily digest"* loop that `RESEARCH-SYNTHESIS.md:79` makes load-bearing. Costs nothing in safety; the LLM's output never touches a number, an order, or a weight.

---

## (d) Top-3 ranked by value × safety × cost

| Rank | Use | Plug-in `file:line` | Value | Safety | Cost | Score | Why |
|---|---|---|---|---|---|---|---|
| **1** | **News / adverse-event VETO** | `risk/guardrails.py:194-197` | **High** — directly prevents the catastrophic bad trades the benchmarks show (70%+ DD) | **Highest-in-class** — bounded to opportunity cost; a wrong veto just skips a trade (TradeTrap `2512.02261` proves judgment must be fenced) | **Low** — one call per proposal | ★★★★★ | AI-Trader (`2512.10971`) names risk-control as *the* cross-market differentiator; TradeTrap (`2512.02261`) proves the order path must stay LLM-free. This is the one use with **direct capital-protection** value and an unambiguous literature mandate. |
| **2** | **Unstructured→structured extraction — universe BLACKLIST first** | `universe/scout.py:56-69` (primary), `fleet/orchestrator.py:91-95` (secondary event analyst) | **High** — MEXC is listing/unlock-heavy; prevents entering bad names *before* they reach the order path; covers analyst blind spots (`agents/sentiment.py:26-30` is a stub) | **High** — veto-only, never order-routing; the blacklist variant sits upstream of execution entirely | **Low** — batch extraction, cached/calendar-driven | ★★★★☆ | FinAgent (`2402.18485`) + FinGPT (`2306.06031`) are at base extraction contributions. The **blacklist** form is safer than the **analyst** form — ship that first. Mild alpha-extension is a bonus, not the point. |
| **3** | **Post-hoc digest / report generation** | `agents/auditor.py:27-55` (+ `fleet/memory.py:126-127` rendered to prose) | **Medium** — process/compliance value; sharpens the load-bearing human-review loop (`RESEARCH-SYNTHESIS.md:79`) | **Highest possible** — zero order-path interaction; ledger is read-only input | **Lowest** — ~one call/day | ★★★★☆ | FinGPT/FinRobot are, functionally, report platforms (`2306.06031`, `2405.14767`). Zero downside, real workflow value — the obvious Phase-1 starter. |

**Deferred (Phase-2): Regime classification (c2)** ranks **4th** — high *theoretical* value (agent-05 calls it the path from curve-fit to real adaptive edge, `05-fleet-llm-edge.md:92,96`) but higher implementation risk (regime labels feed `ReflectionMemory.weight`, which *does* touch sizing) and higher per-cycle cost. Live only after (1)–(3) are proven.

**Why veto > extraction > digest (all three are safe):** they share the safety property, so the ranking reduces to **directness of capital protection**. VETO stops a losing trade *at the gate*; extraction stops a bad name *entering the universe*; digest improves a human's ability to supervise. Capital-protection value decreases across that ordering, so the score does too.

---

## (e) Sources (all fetched live ✅ this session)

- ✅ TradingAgents — Xiao et al., 2024 — `https://arxiv.org/abs/2412.20138`
- ✅ FinGPT — Yang, Liu, Wang, 2023 (IJCAI FinLLM Symposium, Best Presentation) — `https://arxiv.org/abs/2306.06031`
- ✅ FinAgent — Zhang et al., 2024 — `https://arxiv.org/abs/2402.18485`
- ✅ FinRobot — Yang et al., 2024 (Whitepaper V1.0) — `https://arxiv.org/abs/2405.14767`
- ✅ LiveTradeBench — Yu, Li, You, 2025 (UIUC-DAIS-TR-25) — `https://arxiv.org/abs/2511.03628`
- ✅ AI-Trader — Fan et al., 2025 (HKUDS) — `https://arxiv.org/abs/2512.10971`
- ✅ TradeTrap — Yan et al., 2025 — `https://arxiv.org/abs/2512.02261`
- Repo base facts: `RESEARCH-SYNTHESIS.md:11,38,39,65,79,114` · `05-fleet-llm-edge.md:92,96,100-134`

---

## (f) Honest summary / calibration

**Is:** the literature (3 live benchmarks + 4 system papers) converges on a single non-predictive LLM role — **schema-fenced gatekeeper (veto / classify / extract / report), never predictor**. The top-3 rapana plug-ins are: **news-veto at `risk/guardrails.py:194-197`**, **event-extraction blacklist at `universe/scout.py:56-69`**, **digest prose at `agents/auditor.py:27-55`**. All three already exist as seams in the codebase and all three keep the LLM out of the order path.

**Is not:** a reason to expect LLM alpha. The 3 live benchmarks (LiveTradeBench `2511.03628`, AI-Trader `2512.10971`, TradeTrap `2512.02261`) are unanimous that predictive edge fails OOS; the 4 system papers' returns are backtested and assumed to decay.

**Calibration notes:** (i) Every abstract was fetched live; I did **not** re-fetch the full PDFs, so per-component numbers (e.g. FinAgent's "92.27%" / "+36%") are quoted from the abstracts and are **backtested** — treated here as non-OOS. (ii) The "regime classification is the highest-upside *theoretical* use" claim inherits from `05-fleet-llm-edge.md:92,96` (an inference, not a code-verified fact) and is down-ranked to Phase-2 here for that reason. (iii) The "surveys" breadth is satisfied by the 3 benchmark papers, which are themselves cross-model surveys (21 LLMs / 6 LLMs / multiple agent types); no separate standalone LLM-finance *survey* paper was fetched.
