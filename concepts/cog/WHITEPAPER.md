# THE COG

## A Capability-Indexed Unit of Account for the Intelligence Economy

*Draft 0.2 — June 2026 — ProofOfWorks*

---

## Abstract

The price of cognition falls roughly 5× per year at the frontier tier and up to an order of
magnitude per year at the commodity tier (§1, Appendix C). Every AI contract
denominated in dollars is therefore mispriced within months of signature: the buyer is
unknowingly **short AI progress**, the seller is unknowingly long it, and neither party chose
that bet. The result is a market-wide failure: buyers refuse long-term AI contracts, sellers
can't sell them, and the agent economy — which needs millions of standing service agreements
between parties that can't renegotiate over dinner — has no stable unit to write them in.

We propose **the cog**: a non-circulating, daily-published unit of account defined as *the
verified market price of executing a frozen reference cognitive workload at a frozen capability
threshold*. The cog is not a currency, not a token, and not a blockchain. It requires no
consensus mechanism and violates no trilemma. It is a measuring stick — the metre of the
intelligence economy — modeled on the one indexed unit of account with a 60-year production
track record: Chile's Unidad de Fomento, in which an entire national mortgage market is
denominated. The UF protects contracts from the *inflation of money*. The cog protects
contracts from the *deflation of intelligence*. It is, as far as we can determine, the first
deflation-native unit of account ever proposed.

---

## 1. The Bending Ruler

A unit of account is a ruler for value. Rulers are useful because they don't bend.

For the intelligence economy, the dollar is a bending ruler. Documented constant-quality
price points:

| Date | Cheapest model at tier | Blended price* | Source |
|---|---|---|---|
| Nov 2021 | GPT-3 davinci (MMLU ~42 tier) | $60.00 / M tokens | a16z "LLMflation" |
| Nov 2024 | Llama 3.2 3B (same tier) | $0.06 / M tokens | a16z "LLMflation" |
| Mar 2023 | GPT-4 (frontier tier) | $36.00 / M tokens | OpenAI launch pricing |
| Aug 2024 | GPT-4o | $4.00 / M tokens | OpenAI |
| Dec 2024 | DeepSeek-V3 | $0.44 / M tokens | DeepSeek |
| Sep 2025 | Grok 4 Fast (AA-II > 60) | $0.26 / M tokens | Artificial Analysis |
| Jun 2026 | DeepSeek V4 Flash (provisional) | $0.12 / M tokens | OpenRouter, live |

\* *Blended = 0.8 × input + 0.2 × output price per million tokens (4:1 ratio). See Appendix C
for the full table with caveats.*

That is a **1,000× decline in three years** at the lower tier (a16z's measurement — exactly
10×/yr) and **143× in 39 months** at the frontier tier (ours — 4.6×/yr, computed by
`cogfix/cogfix.py` over the non-provisional series). Counting the provisional June-2026 point
the frontier figure is 305× (5.8×/yr), but that point is excluded from the official fix until
it clears a qualifying basket run, so the conservative number is the one to quote.
Call it **4.6–10× per year depending on tier**.
This is faster than transistor prices fell during Moore's Law, faster than bandwidth fell
during the dot-com buildout.

Now consider what this does to every contract written in dollars:

**The worked example.** In May 2024 you sign a 24-month contract for an AI document-processing
service: $10,000/month, fixed. The service consumes ~1 billion blended tokens/month of
GPT-4o-class inference, which costs the vendor ~$7,000 at signing. Fair price, thin margin.
By spring 2026 the same cognition costs the vendor ~$254. You are still paying $10,000. The
contract has silently become ~97% gross margin. Across the full term you overpay **$195,409 —
81% of the $240,000 contract** (computed in `cogfix/cogfix.py`). You were short AI progress;
you lost.

The market already knows this in its bones, which is why the observable equilibrium is:

- **No long-term AI contracts.** Buyers cap terms at 12 months or demand renegotiation
  clauses, which are themselves repricing fights waiting to happen.
- **Sandbagging suspicion.** When a vendor's costs drop 10×, do they pass it on? Buyers
  assume not, and trust collapses.
- **Agent paralysis.** Autonomous agents signing service agreements with other agents have
  no human to renegotiate for them. A standing agreement between two agents denominated in
  USD is a time bomb with a ~6-month fuse.

The deeper point: **every USD-denominated AI obligation embeds an unchosen derivative
position on the rate of AI progress.** Fixed-price buyers are short progress. Fixed-price
sellers are long it. Insurance, escrow, SLAs, employment-shaped agent contracts, compute
commitments — all of them carry this hidden leg. A trillion-dollar market is being built on
a ruler that bends 10× a year, and everyone is pretending not to notice.

Chile noticed, in 1967, that writing mortgages in a currency inflating 20%+/year was
impossible — so the central bank began publishing the **Unidad de Fomento**, a daily
CPI-indexed unit of account. Nobody holds UF. Nobody pays in UF. But mortgages, rents, and
long-term contracts are *written* in UF and settled in pesos at the day's published value.
It works so well that 60 years later it is simply how Chile prices anything long-term.

The intelligence economy has the same disease with the opposite sign. It needs the same cure.

---

## 2. Watts versus Lumens

The obvious objection: "indexes of AI prices already exist." They do — and they measure the
wrong thing.

There is a precise historical analogy. For centuries, light was priced by its *inputs*:
candles, gas, then watts of electricity. As lighting efficiency exploded (a candle to an LED
is a ~1,000× efficiency gain), pricing light in watts became meaningless — so the industry
moved to the **lumen**, a unit of light *output*. You don't buy electricity when you want
light; you buy lumens.

Token-price indexes — e.g. compute.finance's Standard Compute Unit, a weighted average of
posted per-token prices across providers — price cognition in **watts**. They answer "what
does a token cost?" But a 2026 token buys ~100× the cognition of a 2021 token. A token-price
index systematically *understates* the deflation of intelligence, because the quality packed
into each token is itself rising. Tokens are an input. Nobody wants tokens; they want tasks
done.

The cog prices cognition in **lumens**: the cost of achieving a *fixed capability outcome*,
regardless of which model, provider, or architecture delivers it. The a16z LLMflation
analysis and Artificial Analysis's "cheapest model above intelligence tier X" tracking both
already measure in lumens — but as observations, charts, leaderboards. Nobody has turned the
lumen of intelligence into a *unit you can write a contract in*. That is the entire gap, and
it is the entire idea.

---

## 3. The Unit

**Definition (COG-1).**

> **1 cog** = the *depth-verified* market price, on the fix date, of running the
> **COG-1 Reference Workload** on any model that passes the **COG-1 Capability Basket** —
> the volume-weighted median of receipted qualifying runs, not the cheapest sip.

Three frozen components:

**(a) The Capability Basket** — a frozen evaluation suite and threshold defining
"qualifying intelligence." For COG-1 we propose: a public core (for reproducibility) drawn
from established evals, plus a private rotating audit set (for contamination detection),
with the threshold set at roughly *GPT-4-class* general capability — the tier with the
longest clean price history. A model qualifies on a fix date if it meets the threshold on
the public core and the private-audit divergence is below ε.

**(b) The Reference Workload** — 1,000,000 blended tokens (800k input / 200k output) of
inference on a frozen task-mix distribution, executed at qualifying capability. The workload
is what a contract's quantity is measured in: a job that takes 40M blended qualifying tokens
is a 40-cog job, *forever*, by construction.

**(c) The Fix** — the daily published USD (or any currency) price of 1 cog. Critically, the
fix is **not** computed from posted prices. Posted prices can be manipulated by quoting
rates nobody can actually transact at — the LIBOR disease. Instead:

> Each fix day, fixers *actually purchase* the Reference Workload from candidate providers
> and publish **execution receipts** — request hashes, token counts, billing evidence, and
> eval-pass evidence. A price enters the fix only with **depth, not a sip**: at least
> K independent purchases (draft K = 5) of at least N tokens each (draft N = 10M), spread
> across the fix window. The fix is the **volume-weighted median** of receipted qualifying
> runs — never the cheapest single run — smoothed as a 7-day median and, with multiple
> independent fixers, taken as the cross-fixer median.

The depth requirement is what makes the number mean *capacity*, not a promotional sip: a
cheap 1M-token run proves a price existed for one request; K sized buys across the window
prove the market would actually sell you cognition at that price, repeatedly, at scale.
The oracle's answer to "how do we know?" is not "trust our survey." It is: **"we bought
intelligence today, in size; here are the receipts."** A daily fix costs a fixer roughly
$10–15 of inference at current prices (five sized buys) — still the cheapest credible price
oracle ever proposed, because the thing being priced is itself nearly free to sample.

### What the cog is not

- **Not a currency.** Nothing circulates. No tokens, no wallets, no supply.
- **Not a blockchain.** Publication can be a signed JSON file on a website; mirroring
  on-chain is optional plumbing. There is no consensus problem because there is no state
  to agree on beyond a signed daily number with receipts — anyone can recompute it.
- **Not a price cap or a benchmark mandate.** It is a measuring stick. Parties remain free
  to price above or below it; they simply gain a stable unit to do so *in*.

This design deliberately sidesteps the decentralized-money trilemma: a unit of account
needs no scarcity, no double-spend prevention, and no global consensus. It needs only
*reproducible measurement* — which is a solved-ish problem (metrology) rather than an
impossible one (trustless distributed cash).

---

## 4. The Contracting Layer

The unit becomes infrastructure the moment two parties denominate an obligation in it.

**The worked example, repriced.** Same deal: the workload is 1B blended qualifying
tokens/month = 1,000 cogs/month. Vendor wants a 43% markup (30% gross margin) and says so
openly: price = **1,430 cogs/month, 24 months, settled monthly in USD at the published fix.**

- May 2024 fix = $7.00 → month-1 invoice ≈ **$10,010**. Same as before.
- Month-24 fix ≈ $0.254 → final invoice ≈ **$363**.

The buyer's bill fell 96% *automatically*, tracking the true cost of cognition. The vendor
earned exactly the agreed real margin every single month. Nobody renegotiated. Nobody
sandbagged. Nobody was secretly short or long AI progress. The contract did what contracts
are for: it removed a bet neither party wanted.

That is the *mechanics*, isolated for clarity — and it is deliberately **not** the
production template, because a pure-cog contract drowns the vendor. Only inference deflates
10×/year; the vendor's humans, support, SLAs, and compliance do not, and a month-24 invoice
of $363 pays no salaries.

**The hybrid template (the one that survives contact with a CFO).** Index only the volatile
leg — the fuel-surcharge pattern, the COLA-clause pattern, the steel-escalator pattern. The
same $10,000/month deal is structured as:

> **$3,000/month fixed (people, support, compliance) + 1,000 cogs/month (the cognition
> leg), settled monthly in USD at the published fix.**

Month-1 invoice: $10,000 — identical to the fixed deal. Month-24 invoice: **$3,254** — the
people-leg intact, the cognition leg at market. Over the full term the buyer pays
**$103,214 instead of $240,000** (computed: `cogfix/cogfix.py --contract 10000 24 2024-05
--fixed 3000`). Every dollar of cognition deflation passes through; the vendor's payroll
never deflates. Index what deflates; pay salaries in salary-money.

**Why sellers sign this — the honest version: mostly, they don't volunteer.** The silent
97%-margin contract of §1 is not a market failure from the vendor's chair; it *is* the
business model, and nobody surrenders margin expansion out of principle. The unit spreads
through three forces that require no vendor virtue:

1. **Agents first.** In agent-to-agent SLAs there is no salesperson defending margin and no
   procurement theater — both sides are code, and code adopts whatever the default template
   is. A standing agreement between two agents *needs* an auto-repricing unit, because no
   human exists to renegotiate it. Cog denomination there is the path of least resistance,
   not a concession. This is the wedge, and Phase 2 leads with it.
2. **Buyers force it.** Once one serious procurement team puts a cog rider in an RFP,
   "we don't do indexed pricing" reads as "we intend to keep the deflation." Fuel
   surcharges, steel escalators, and COLA clauses all became standard the same way: imposed
   by the side carrying the unwanted risk, then normalized into boilerplate.
3. **Challengers weaponize it.** The hungry #3 vendor offers cog pricing to break the
   incumbent's silent-margin annuity — *"they keep the deflation; we pass it through"* is a
   sales weapon that costs the challenger little (its margin was thinner anyway).
   Competition does the rest.

Once forced to the table, sellers do collect real consideration: **term length** (buyers
refuse multi-year AI deals today precisely because of deflation fear — indexing deletes the
fear, and the hybrid template means only the leg that should deflate does), **symmetric
protection** (if cognition costs ever *rise* — GPU shortage, energy crunch, export controls
— the fix rises and the seller is covered), and **honest, defensible margins** ("1,430 cogs
for a 1,000-cog workload" states markup in public units, and a vendor running *below* fix
cost keeps every basis point of its efficiency edge).

**Where it lands first:**

- **Agent-to-agent commerce.** Standing service agreements between autonomous agents,
  escrow, and SLAs need a unit neither agent controls and neither agent's principal must
  renegotiate. Cog-denominated obligations settle over existing rails (stablecoins, x402)
  at the day's fix — and pair naturally with verified-delivery receipt schemes for the
  *did-the-work-happen* half of settlement.
- **AI insurance and guarantees.** Underwriting an agent's performance over 24 months in
  USD is underwriting an unknown deflation curve. In cogs, exposure is constant in real
  cognition terms.
- **Compute take-or-pay and capacity deals.** The spread between cogs (outcome) and
  GPU-hours (input) is the *algorithmic-efficiency premium* — currently unpriceable,
  instantly priceable once both legs have units. A 2026 arXiv line of work on AI token
  futures already gropes toward quality-standardized contracts the way crude oil
  standardized on API gravity and sulfur content; the cog is the missing settlement index
  under such derivatives.
- **Governments and statistics agencies.** "Cost of cognition" belongs in national accounts.
  A reproducible, receipted index is how it gets there.

---

## 5. Basket Versioning, or: How Rulers Survive

Every fixed basket decays. Evals leak into training data; thresholds saturate; the task mix
drifts from what the economy actually buys. This is not a flaw discovered by critics — it is
the central engineering problem, and metrology solved it long ago. The metre has been
redefined four times (bar → krypton wavelength → speed of light) without any contract
written in metres breaking. CPI baskets are substituted and **chain-linked** continuously.

The cog inherits the standard machinery:

- **Versioned baskets.** COG-1 today. When contamination drift (public-core vs private-audit
  divergence > ε) or saturation triggers review, COG-2 is minted with a *new* frozen basket.
- **Overlap windows.** COG-1 and COG-2 fixes are published in parallel for ≥ 6 months,
  establishing an empirical **linking factor** (the metre/CPI trick). Contracts written in
  COG-1 either run off in COG-1 or convert at the published link.
- **Sunset by contract, not by fiat.** A basket version is published for as long as
  obligations reference it.
- **Private rotating audit set.** A small held-out eval slice, refreshed per period and
  disclosed after use, exists *only* to detect that the public core has been gamed — the
  ARC-style semi-private pattern. It never sets the fix; it only triggers version review.

---

## 6. Failure Modes (and why they're survivable)

**Goodhart / benchmark gaming / loss-leader manipulation.** A provider overfits the public
core to qualify cheaply, or subsidizes a below-cost endpoint to drag the index. Mitigations:
private audit divergence check; the **depth requirement** (the gamed or subsidized model
must actually serve K sized buys at the quoted price, on demand, across the window — a
loss-leader pays real money to serve *every* taker, every day, for as long as it wants to
move the fix); and **volume-weighting**, which caps how far any single cheap endpoint can
pull the median. Multi-fixer procurement hits production endpoints, not demo endpoints.
Residual risk: real, managed, versioned away when detected — same as CPI substitution bias,
a managed nuisance rather than a refutation.

**"Capability isn't a scalar."** Correct, and the cog doesn't claim it is. The cog prices
*one frozen tier of general capability* — deliberately the commodity tier, where competition
is thickest and the price signal cleanest. Specialized capabilities (vision, long-horizon
agency, formal math) can get sibling units (COG-V, COG-A…) with their own baskets if the
market demands them. The dollar didn't need to be all things either; it needed to be one
agreed thing.

**Fixer capture / oracle trust.** The methodology is deterministic and the inputs are
receipted, so any party can become a fixer and any party can audit one. Trust concentrates
in math and receipts, not institutions; the median across independent fixers bounds
manipulation by any minority. This is LIBOR's lesson applied: transaction-based, not
submission-based.

**Negotiated vs posted prices.** Big buyers pay below posted rates. The fix measures the
*marginal public price* of qualifying cognition — the right benchmark for the same reason
LIBOR measured marginal interbank rates, not sweetheart deals. Contracts can specify
fix-relative pricing (e.g. "0.85 × fix") exactly as floating-rate debt specifies
"SOFR + 120bp."

**Tokens-per-task drift (the "token cost illusion").** Per-token prices fall, but newer
models often spend *more* tokens per task — longer context, reasoning traces, tool calls —
so a buyer's job cost can fall slower than the fix. The cog does not pretend otherwise: it
prices a frozen token workload at frozen capability, which is a well-defined unit, not a
promise about your pipeline's efficiency. Contracts whose quantity is naturally task-shaped
should define the deliverable in tasks and let the vendor carry token-efficiency risk — or
adopt a future task-denominated sibling (COG-T: a frozen basket of completed reference
tasks) once eval harnesses are reproducible enough to receipt task completions.

**Vendor cost-structure mismatch.** Only the cognition leg of an AI service deflates;
people, support, and compliance don't, so a pure-cog contract starves the vendor by year
two. Resolved by construction in the hybrid template (§4): fixed USD for the human leg,
cogs for the volatile leg only.

**What if deflation stops?** Then the cog goes flat and cog contracts behave like USD
contracts. The unit costs nothing when it isn't needed. (Its option value, like the UF's,
is realized precisely when the ruler would otherwise bend.)

**Chicken-and-egg adoption.** The UF playbook again: it started in 1967 as an obscure unit
for development loans, got mortgages in the 70s–80s, and ate the economy. The cog's wedge
is narrower and faster: AI-service procurement templates and agent-to-agent SLAs, where the
pain is acute, the parties are sophisticated, and one fix publisher with receipts is enough
to start.

---

## 7. Prior Art (honest map)

| Thing | What it is | What it lacks |
|---|---|---|
| **Chile's UF (1967)** | Daily inflation-indexed unit of account; national mortgage market runs on it | Indexes money's inflation, not cognition's deflation — the template, not the thing |
| **SDR, inflation-linked bonds, chained CPI** | Indexed-unit machinery, chain-linking practice | Same — wrong underlying |
| **The lumen (1924 CIE)** | Output-unit replacing input-pricing of light | Not money infrastructure; the metaphor and the precedent |
| **a16z "LLMflation" (2024)** | Constant-quality price observation, ~10×/yr decline | A chart, not a unit; no fix, no methodology, no contracts |
| **Artificial Analysis tier tracking** | "Cheapest model above intelligence X" time series | A leaderboard; posted prices; not contractable |
| **compute.finance SCU (2025)** | Token-price index, on-chain oracle | Prices watts (tokens), not lumens (capability); explicitly not quality-adjusted; not a unit of account |
| **AI token futures / "Standard Inference Token" (arXiv 2026)** | Academic futures design — contract specs, margins, settlement — around a standardized token unit (SIT) | A derivatives blueprint on paper: the SIT is a contract-spec unit, not an operating index — no fix, no receipts, no published number, no service-contract layer. Nearest conceptual neighbor; validates the need |
| **Proof-of-useful-work coins, compute-backed tokens** | Currencies backed by computation | Currencies — they fight the trilemma; the cog deliberately isn't one |

**The claim of novelty, precisely:** the *fusion* is new — (capability-normalized outcome
pricing) × (execution-receipt-verified daily fix) × (unit-of-account contracting layer).
Each ancestor has one leg. Nothing we could find has two, let alone three, and the term
"deflation-native unit of account" appears to be unclaimed entirely.

---

## 8. Why Now

1. **The deflation is now common knowledge** (LLMflation, Epoch, AA) — but un-instrumented.
2. **Agent-to-agent commerce is arriving** (x402, agent payment protocols, delivery-receipt
   schemes) with no stable unit to denominate standing obligations in.
3. **The index layer is being built by others** (compute.finance proves the appetite) — but
   in watts. The lumens layer, and the unit-of-account layer above it, are unclaimed.
4. **The fix is nearly free to compute.** Pricing a day's cognition costs a few dollars of
   inference plus an eval harness. In 1967 Chile needed a central bank; in 2026 a cog fixer
   needs a cron job and a receipts page.

---

## 9. Roadmap

- **Phase 0 — Reference implementation** (this repo): unit spec, historical backtest,
  fix calculator with live provider data, contract repricer. Done.
- **Phase 1 — The Fix, published** *(started 2026-06-09: first ssh-signed quote-mode fix,
  $0.144, via `fixer/fixerd.py`)*: daily COG-1 fix with execution receipts at a public URL;
  signed JSON + archive. One fixer (us), methodology open, anyone can verify or fork.
  Remaining: receipts on, the qualifying harness (replace the assumed allowlist with a
  daily administered capability exam), public hosting, 7-day median series.
- **Phase 2 — Agent SLAs first, then enterprise riders**: hybrid-denomination templates
  ("$F/month fixed + N cogs/month, settled monthly in USD/USDC at the published COG-1
  7-day median fix"). Agent-to-agent standing agreements lead — no human defends margin
  there, and defaults win; enterprise MSA riders follow on buyer procurement pressure.
  Settlement plumbing over stablecoin rails; pairs with verified-delivery receipts for
  full *priced-and-proven* agent settlement.
- **Phase 3 — Plurality**: independent fixers, cross-fixer median, COG-2 process, sibling
  units if demanded, and — if the futures people are right — cogs as the settlement index
  for intelligence derivatives.

---

## Appendix A — COG-1 draft parameters

| Parameter | Value (draft) |
|---|---|
| Capability threshold | GPT-4-class general tier (frozen eval core + threshold published at v1.0) |
| Reference workload | 1M blended tokens: 800k in / 200k out (4:1), frozen task-mix |
| Qualifying evidence | Public-core pass + private-audit divergence < ε + production endpoint |
| Fix | Volume-weighted median of receipted qualifying runs; 7-day median smoothing; cross-fixer median with multiple fixers |
| Depth requirement | ≥ K = 5 independent purchases of ≥ N = 10M tokens each per window (draft) — a sip cannot set the fix |
| Contract template | Hybrid: $F/month fixed (non-AI legs) + N cogs/month (cognition leg) |
| Publication | Daily, signed JSON: `{date, fix_usd, model, receipts[], basket: "COG-1"}` |
| Version trigger | Audit divergence > ε, saturation, or task-mix obsolescence review |
| Chain-linking | ≥ 6-month parallel publication; linking factor = median fix ratio over window |

## Appendix B — Roads deliberately not taken

- **A new L1 / better Bitcoin** — previously investigated and judged impossible under the
  decentralization trilemma. The cog needs no consensus and inherits none of that burden.
- **Mutual credit / multilateral netting** — previously investigated and junked as a
  rediscovery (LETS/Sardex). Not resurrected here; the cog touches no credit creation.
- **Probabilistic micropayment settlement (Peppercoin revival for agents)** — genuinely
  viable now that risk-neutral high-frequency agents exist, but it is a *revival* of
  Rivest–Micali 2002, not an invention. Noted as adjacent future work, possibly as a
  settlement optimization *under* cog-denominated obligations.

## Appendix C — Backtest data and caveats

Full table in [`cogfix/data.json`](cogfix/data.json), with per-point sources. Caveats:
pre-2025 points use launch-announcement pricing (documented); capability tiers are
approximated by MMLU-era public scores rather than a true frozen COG-1 basket run (which
did not exist historically — the backtest shows the *shape* the fix would have had, labeled
approximate throughout); 2026 points are live OpenRouter quotes fetched 2026-06-10, with
the V4-Flash point marked *provisional pending a qualifying basket run*.

---

*The metre survived four redefinitions. The dollar survived the gold window. Light survived
the switch from watts to lumens — and lighting got a thousand times cheaper while the unit
held still. Intelligence is getting a thousand times cheaper. Hold the unit still.*
