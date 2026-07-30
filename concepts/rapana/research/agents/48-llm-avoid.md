# 48 — The honest case AGAINST LLM/agent autonomous trading alpha (do-not-build list)

**Agent:** 48/60 (SKEPTIC / anti-pitfall) · **Scope:** enforces the "LLM is not the alpha source" boundary across `rapana/fleet/orchestrator.py`, `rapana/agents/`, `rapana/risk/guardrails.py`, `rapana/fleet/portfolio.py`, `rapana/fleet/memory.py`
**Goal:** Document **why** LLM price-prediction / autonomous order-routing fails, so the team does **not** waste effort on it, and produce an explicit **do-not-build** list the synthesis will enforce.

All repo citations are `file:line`. All paper citations are arXiv `id` + URL — **every abstract was fetched live this session ✅** (LiveTradeBench, AI-Trader, TradeTrap). This note is the *negative-space* companion to `32-llm-papers.md` (which catalogues the viable non-predictive uses) and `05-fleet-llm-edge.md` (the gatekeeper design). It exists to kill the recurring "let the agent trade" idea at the evidence level.

The two base facts the whole argument rests on are already multiply-cross-verified in the repo: **best LLM ~6% over 50 days, peers 70%+ drawdowns** (LiveTradeBench, `2511.03628`; `RESEARCH-SYNTHESIS.md:39`) and **925,323 AI-agent wallets net −$191.7M** (`RESEARCH-SYNTHESIS.md:11,114`).

---

## (a) Evidence table — the failure numbers, with sources

| # | Claim | Number | Source (fetched ✅ / repo base) | URL |
|---|---|---|---|---|
| 1 | Best LLM in a 50-day **live** test returned ~6%; peers took **70%+ drawdowns**; authors decline to claim reliable alpha | ~6% / 50d best; 70%+ DD | LiveTradeBench (21 LLMs, live) `2511.03628` ✅ · `RESEARCH-SYNTHESIS.md:39` | https://arxiv.org/abs/2511.03628 |
| 2 | "High LMArena scores **do not imply** superior trading outcomes" — general intelligence ≠ trading ability | qualitative (21 models) | LiveTradeBench `2511.03628` ✅ | https://arxiv.org/abs/2511.03628 |
| 3 | "**Large reasoning models do not confer trading advantages**" — CoT/reasoning models did *not* beat non-reasoning peers | qualitative | LiveTradeBench `2511.03628` §5.3 ✅ | https://arxiv.org/abs/2511.03628 |
| 4 | "Most agents exhibit **poor returns and weak risk management**"; "**risk control capability determines cross-market robustness**" | most of 6 LLMs lose; risk-control is the differentiator, not prediction | AI-Trader (live, data-uncontaminated, US+A-shares+crypto) `2512.10971` ✅ | https://arxiv.org/abs/2512.10971 |
| 5 | "Small perturbations at a single component … induce **extreme concentration, runaway exposure, and large portfolio drawdowns**" — LLM judgment is fragile & adversarially manipulable in the order path | catastrophic under perturbation | TradeTrap (adversarial stress-test) `2512.02261` ✅ | https://arxiv.org/abs/2512.02261 |
| 6 | **925,323** AI trading-agent wallets produced a **net −$191.7M loss** (population-level) | −$191.7M / 925,323 wallets | "Paper Agents, Paper Gains" study · `RESEARCH-SYNTHESIS.md:11,114` (via TheStreet/Yahoo coverage; cross-verified by Codex fleet, `RESEARCH-SYNTHESIS.md:120`) | (synthesis base fact; coverage cited `RESEARCH-SYNTHESIS.md:114`) |
| 7 | Backtest→live edge **decay is 30–80%**; overfitting is endemic | 30–80% decay | `RESEARCH-SYNTHESIS.md:38` | — |
| 8 | Cost drag: ~0.2% round-trip + funding; "a few round-trips/day can bleed several %/month *before* any edge" | several %/month drag | `RESEARCH-SYNTHESIS.md:37` | — |

**Reading the table:** of the named literature, only the **three live, contamination-controlled benchmarks** (rows 1–5) test out-of-sample. **All three reject LLM predictive alpha** from different angles (low absolute returns → fragility → adversarial exploitability). The four system/platform papers (TradingAgents/FinGPT/FinAgent/FinRobot, catalogued in `32-llm-papers.md:28-31`) report only **backtested** returns, which row 7 says decay 30–80% — so their headline numbers do **not** survive the live test. Row 6 is the population-level confirmation: not "LLMs underperform a benchmark" but "925k real agent wallets lost ~$192M net."

---

## (b) Root causes — *why* it fails (not just *that* it fails)

These are the mechanisms behind the numbers. Each maps to a rapana design choice that must stay closed.

1. **No informational edge over price.** An LLM ingests the same public tape (price, news, social) every other participant sees; price already aggregates that information (EMH, weak-form at minimum on liquid majors). The repo's own words: *"an LLM has no informational edge over price"* (`RESEARCH-SYNTHESIS.md:39`). Where edge *does* exist in this project — funding-fee reversion, maker rebates, listing microstructure (`32-llm-papers.md:40`) — it is **structural/venue-specific**, not something an LLM "reasons" into. → rows 1, 2, 6.
2. **"Reasoning" is post-hoc narrative, not discovery.** LiveTradeBench is explicit: *"Large reasoning models do not confer trading advantages"* (row 3). Chain-of-thought produces a *plausible story after the fact*; it does not manufacture information the model doesn't have. More thinking tokens → more confident narrative, not more edge. This is why GPT-o3 / DeepSeek-R1 did **not** beat their non-reasoning peers. → rows 1, 3.
3. **Hallucinated state.** LLMs confabulate position/fill/ledger state under multi-turn load. TradeTrap independently names **"portfolio and ledger handling"** as one of the four components that fails under perturbation (`2512.02261`). A model that "remembers" a fill that didn't happen will size the next order on fiction. → row 5.
4. **Prompt injection / tool hijack.** TradeTrap's whole thesis: untrusted external data (news/social/on-chain) at the **market-intelligence** or **execution** component propagates through the loop into *"runaway exposure"* (row 5). Any unconstrained tool call (fetch URL, read tweet, parse HTML) is an injection surface; on MEXC's listing-heavy, narrative-driven small-caps the adversarial content density is high. → row 5.
5. **Latency.** LLM inference is on the order of seconds; MEXC microstructure moves in milliseconds. Any directional "read" is stale by the time the token streams, and the perp funding/orderbook the model reasoned about has already moved. On a venue that officially restricts HFT/arbitrage (`RESEARCH-SYNTHESIS.md:15`) you are not winning a speed game with an LLM in the loop. → rows 1, 4.
6. **Per-decision cost vs expected value.** Inference is billed per call; expected value per directional decision is ~zero (rows 1, 6). At even one call per symbol per cycle, token cost stacks on top of the cost-drag in row 8, eroding the thin structural edge that does exist. An LLM that is right 51% at $0.02/call loses to no-LLM once drag is included. → rows 1, 6, 8.
7. **Overfitting & backtest→live decay.** Prompt-engineered "strategies" are curve-fit to the sampled period; the 30–80% decay in row 7 applies to *prompts* just as much as to ML models. A strategy that "worked in backtest because the LLM read hindsight-contaminated news" is the canonical failure (information leakage, `32-llm-papers.md:18`). → rows 1, 7.

**Synthesis of mechanisms:** rows 1–2 kill the *premise* (no edge to be found), rows 3–5 kill the *implementation* (state/injection fragility), rows 6–7 kill the *economics* (cost + decay). There is no layer of the stack where autonomous LLM trading survives.

---

## (c) DO-NOT-BUILD list for rapana (explicit, enforced by the synthesis)

Each item states the dead-end, the evidence against it, and the **existing code invariant** that already blocks it (and must not be removed). These are the five enumerated dead-ends, hardened against the evidence above.

### (c-a) DO NOT use the LLM as a primary / high-weight directional signal
- **What's tempting:** feed the LLM's "bullish/bearish" call into `weighted_combine` as a high-`source_weights` source.
- **Evidence against:** rows 1, 2, 3, 6 — predictive edge fails OOS; reasoning models confer no advantage; 925k wallets net-negative.
- **Invariant already in place:** the Bull/Bear debate is **explicitly advisory** — PM docstring: *"narrative research informs humans; deterministic math moves capital"* (`rapana/agents/portfolio_manager.py:46-51`; debate consumed at `researchers.py:40-46` but never enters `signals.py:87-104`). Any future `LLMEventAnalyst` is hard-capped at `max_weight=0.10` (`portfolio_manager.py:23,59`; `32-llm-papers.md:76`). **Do not raise that cap and do not let LLM output enter `weighted_combine` above a noise-floor weight.**

### (c-b) DO NOT let the LLM size or route orders (side / qty / price / weight)
- **What's tempting:** "let the agent decide position size and which executor to use."
- **Evidence against:** row 5 — TradeTrap proves order-path LLM judgment → *"extreme concentration, runaway exposure, large drawdowns."* This is the single most dangerous dead-end.
- **Invariant already in place:** only `PortfolioManager.decide` constructs a `TradeProposal` (`risk/guardrails.py:41-56`); the LLM classes never import it (`05-fleet-llm-edge.md:186`). The deterministic risk gate (`guardrails.py:189-233`) vetoes, and the kill switch is out-of-band (`guardrails.py:104-126`). **The LLM output contract must stay `{regime|veto|event|digest_prose}` — never `side/qty/price/order`** (`05-fleet-llm-edge.md:150-157`).

### (c-c) DO NOT trust the LLM to track state (positions / fills / PnL / ledger)
- **What's tempting:** let the agent "remember" its book across turns instead of re-querying.
- **Evidence against:** row 5 — TradeTrap names portfolio/ledger handling as a propagating failure point; LLMs confabulate state under load (root cause #3).
- **Invariant already in place:** positions flow from deterministic `PaperPortfolio.apply_fill` (`portfolio.py:31-53`) → `CircuitBreaker.record_realized` (`orchestrator.py:262-268`); the hash-chained ledger (`auditor.py:23-25`) is the only source of truth. **The LLM must never write or hold ledger/position state; it only ever reads a digest (c4 use, `05-fleet-llm-edge.md:130-131`).**

### (c-d) DO NOT make high-frequency / per-tick LLM calls
- **What's tempting:** call the model every tick or every few seconds to "re-evaluate."
- **Evidence against:** root causes #5 (latency, seconds vs ms) and #6 (per-decision cost vs ~zero EV); row 8 cost drag.
- **Invariant / policy:** the LLM's only sanctioned roles are **low-frequency gates** — a news veto is "one call per proposal" (`32-llm-papers.md:96`), the digest is "~one call/day" (`32-llm-papers.md:98`), regime classification is per-symbol-per-cycle not per-tick (`05-fleet-llm-edge.md:108`). **Do not add a hot-path LLM loop. Batch/calendar-driven, cached calls only.**

### (c-e) DO NOT grant unconstrained tool use / free-form action space
- **What's tempting:** give the agent a generic "call any tool / fetch any URL / run any function" interface.
- **Evidence against:** row 5 — TradeTrap's entire finding is that *unconstrained components are exploitable*; prompt-injection / tool-hijack is a documented attack surface (root cause #4). On MEXC's listing/narrative-driven small-caps, adversarial content is plentiful.
- **Invariant already in place:** per `PLAN.md:127-130` (quoted `05-fleet-llm-edge.md:144`): *"External data treated as untrusted; isolated from the action layer. Hard action allow-list; agent cannot exceed a fixed schema regardless of input. High-impact actions require a deterministic policy gate, not model judgment."* **Enforce a hard schema allow-list on every LLM output; fail-soft on anything outside it (mirrors `agents/brain.py:92-95`); never let the model choose which action to take.**

---

## (d) One-line verdict for the synthesis

**The evidence is unanimous and three-source:** LLMs have no informational edge over price, their "reasoning" is post-hoc narrative, and the order-path is adversarially exploitable — so the agent must remain a **schema-fenced gatekeeper (veto / classify / extract / report), never a predictor or router.** The five do-not-build items above are the negative image of the four sanctioned uses in `05-fleet-llm-edge.md:100-134` / `32-llm-papers.md:44-88`; keep the boundary closed and the LLM cannot lose money, only miss trades.

---

## (e) Sources (all fetched live ✅ this session, except the population study which is a repo base fact)

- ✅ LiveTradeBench — Yu, Li, You, 2025 (UIUC-DAIS-TR-25; 21 LLMs, 50-day live) — https://arxiv.org/abs/2511.03628
- ✅ AI-Trader — Fan et al., 2025 (HKUDS; live, data-uncontaminated, US+A-shares+crypto, 6 LLMs) — https://arxiv.org/abs/2512.10971
- ✅ TradeTrap — Yan et al., 2025 (adversarial stress-test of LLM trading agents) — https://arxiv.org/abs/2512.02261
- "Paper Agents, Paper Gains" — 925,323 wallets, ~$191.7M net loss — repo base fact (`RESEARCH-SYNTHESIS.md:11,114`, cross-verified `:120`; via TheStreet/Yahoo coverage)
- Repo base facts: `RESEARCH-SYNTHESIS.md:11,37,38,39,114,120` · `05-fleet-llm-edge.md:144-194` · `32-llm-papers.md:14-18,28-34`

---

*Calibration: rows 1–5 are direct quotes from abstracts/HTML fetched live this session (✅). Row 6 (925k wallets / −$191.7M) is a **repo base fact**, not re-fetched here — it was already multiply-sourced and Codex-cross-verified per `RESEARCH-SYNTHESIS.md:120`; its exact primary URL was not independently reachable via search in this session, so it is cited through the synthesis rather than re-asserted as freshly verified. The five do-not-build items are a **negative-space restatement** of the invariants already documented in `05-fleet-llm-edge.md:183-190` and `32-llm-papers.md`; nothing here is a new code claim — it is the enforcement list.*
