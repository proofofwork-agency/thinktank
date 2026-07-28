# COG — What Would Make This Real

*Draft 0.1 — July 2026 — ProofOfWorks*

This repository contains a specification, a reference implementation, and a worked signed
example. It is **not an operating index**, and nobody should denominate a real obligation in
cogs today. This file is the concrete path from here to there: what must be true, in what
order, what each step costs, and — importantly — **which steps we can do for free right now**
and which ones money cannot substitute for.

Read [`GOVERNANCE.md`](GOVERNANCE.md) alongside this. That file says who controls the number;
this one says what would make the number worth controlling.

---

## The gate

Six things a counterparty should require. None are satisfied today.

| # | Requirement | Status |
|---|---|---|
| 1 | ~90 consecutive daily production fixes | **2 archived days** |
| 2 | Receipts populated — depth gate actually run at spec size | **`receipts: []`, never run** |
| 3 | Endpoint pinning and model fingerprinting | **not implemented** |
| 4 | ≥3 independent publishers or witnesses | **1 publisher, 1 key** |
| 5 | Published operational report: disputes, corrections, tracking error | **none** |
| 6 | Qualifying exam validated as a real GPT-4-class bar | **40-question floor, never run at scale** |

Item 2 is the load-bearing one. The entire argument for COG over an ordinary price index is
"we bought it, here are the receipts." That has never happened.

---

## The critical distinction: metered vs modelled cost

Before any of the phases below, understand this, because getting it wrong would invalidate
everything downstream.

The house proxy ([`sublet`](../../../proxy), same agency) fronts existing CLI subscriptions —
Claude Max, z.ai GLM, Grok, Codex — behind one local endpoint that speaks the OpenRouter
dialect. It is enormously useful and it removes the API-key barrier for most of the work below.

**But a subscription call has no per-token price.** You pay a flat monthly fee. sublet's own
README is explicit: `usage.cost` is *"what the call would have cost metered"* — a figure
**computed from a rate card**, not a price anyone paid.

That means a proxy call gives us:

- ✅ proof the endpoint served the request
- ✅ real token counts
- ✅ real latency, real model behaviour, real refusals
- ❌ **no evidence whatsoever about price**

So:

> **A fix published from subscription-backed calls would be a posted price wearing a receipt's
> clothing.** That is precisely the LIBOR failure COG exists to prevent, and it is the same
> mistake — a label claiming more evidentiary strength than the procedure earned — that this
> repository has now caught in itself four separate times (see `GOVERNANCE.md` §4).

The code enforces this rather than trusting an operator to remember it: price provenance is
tracked as `metered` or `modelled`, and the fixer **refuses** to publish a settleable fix under
`modelled` provenance.

The corollary is the good news. **Capability is not price.** Whether a model passes the
qualifying exam is a fact about the model, and a subscription call establishes it just as well
as a metered one. So the exam — expensive, and never yet run at scale — becomes free.

---

## Phase 0 — free, no API key, do this first

Everything here runs against the local proxy at `http://127.0.0.1:8788/api/v1`. No metered
spend. Start the proxy per its README (`bunx sublet serve`), then:

```sh
export COG_OPENROUTER_BASE=http://127.0.0.1:8788/api/v1
```

**0.1 — Calibrate the exam. (Note: the proxy cannot qualify COG's candidates — read on.)**

The proxy and COG's allowlist have **zero model overlap**, and this is structural rather than
an oversight:

| | models |
|---|---|
| proxy serves | `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4.5`, `glm-5.2`, `glm-4.6`, `grok-4.5`, `gpt-5.6-{luna,terra,sol}` |
| COG allowlists | `deepseek-v3.2`, `deepseek-v4-flash`, `deepseek-v4-pro`, `gpt-4o-mini`, `llama-3.3-70b`, `qwen-2.5-72b` |

The proxy fronts *premium subscriptions*; COG hunts the *cheapest qualifying* tier. They are
looking at opposite ends of the market by design. So the proxy **cannot** sit COG's actual
candidates, and Phase 0 does not include "qualify the allowlist."

What it can do is more useful than it sounds: **test the instrument instead of the candidates.**
Today's exam is 40 questions, and the README already concedes it is "a basic floor, not a proven
GPT-4-class capability gate." Nine frontier models are reachable for free. Sit all nine.

*Acceptance:* a dated exam report for every proxy-reachable model, with the endpoint recorded.
*The interesting outcome is failure to discriminate.* If all nine clear 40 questions comfortably,
the exam does not separate GPT-4-class from anything else — it is a formality, and the
capability gate that the whole unit rests on is not doing its job. That is a finding worth
having, and it costs nothing to obtain.

*Then:* rewrite the exam until it discriminates, using the nine as a calibration set. Only after
that is it worth spending metered money sitting the cheap candidates, because a gate that
everything passes tells you nothing about a DeepSeek model either.

**0.2 — Endpoint identity experiments (gate item 3).** The whitepaper's §6 "endpoint
substitution" section documents a real 5.8× price error from silent realiasing. The proxy makes
this cheap to study: route the same request to the same model slug repeatedly and across
backends, and see what actually varies.

*Acceptance:* a documented, reproducible fingerprinting method, with an honest statement of
what it cannot detect. Do not overclaim — §6 already concedes these controls are statistical,
not cryptographic.

**0.3 — Exercise the fixer end to end under `modelled` provenance.** Prove the plumbing, the
signing, the archive format and the refusal path all work before spending anything.

*Acceptance:* `fixerd --receipt` against the proxy **exits non-zero and refuses to publish a
settleable fix.** If it ever succeeds, that is a bug of the highest severity in this project.

---

## Phase 1 — the depth gate (this is the milestone)

**Money cannot be avoided here, and neither can it be substituted.** This is the one step the
proxy cannot help with, because the thing being established *is* the price.

Run the real protocol: **K = 5 independent purchases of ≥ 10M tokens each**, per fix window,
against metered endpoints, with receipts published.

*Cost:* roughly \$10–15 per fix day at current prices — the whitepaper's own estimate. Call it
**~\$450 for a 30-day run**, less if the cheapest qualifying tier keeps falling.

*Acceptance:* `receipts` is non-empty in the published archive; the fix carries tier
`receipted-depth` **earned rather than inferred**; an independent party can recompute the fix
from the receipts and reach the same number.

*Why this and not more writing:* every remaining claim in the repository is downstream of this.
Until it runs, "depth-verified" is aspirational and the honest description of COG is "a
specification." After it runs — even once — the central claim has been demonstrated.

Note the sequencing: do **0.1 first**. Buying 50M tokens from models that turn out not to
qualify is a waste, and the exam is free.

---

## Phase 2 — duration and independence

**2.1 — Run daily until ~90 consecutive fixes exist** (gate item 1). Cron is already documented
in the README. What matters is that gaps, failures and corrections get published rather than
quietly backfilled — see `GOVERNANCE.md` commitments 2 and 3.

**2.2 — Recruit one independent publisher** (gate item 4). One is worth more than the
specification work already done: it converts "trust our signature" into "compare two." The CDO
schema already supports `publishers[]`, and `settle.py` refuses rules it does not implement, so
the contract layer is ready for a second party before the operation is.

*Honest note:* only `priority-order` is implemented. Cross-publisher median is future work, and
a second publisher is what makes implementing it meaningful rather than speculative.

**2.3 — External attestation of receipts.** Today nobody but us has verified that any buy
happened. A third party re-verifying signatures and recomputing a published fix is a small
favour to ask and a large change in what the index means.

---

## Phase 3 — does it actually track anything

This is the question a CFO asks and the one we currently cannot answer.

`WHITEPAPER.md` §6 states plainly that the cog fix can fall 50% while a given vendor's true
cognition cost falls 10%, and that we have not measured it. Appendix C adds a real result — our
backtest cross-checks against Epoch AI on *pricing* but diverges 2.2–3.2× on *model selection* —
but that is a methodology check on five events, not a tracking-error study.

A real study needs **realized cognition costs from several actual AI businesses over several
periods**. That data does not exist in this repository and cannot be manufactured from it.

*Measure:* correlation, tracking error, volatility, provider concentration, the gap between
posted / executable / negotiated prices, and how often the fallback ladder fires.

*And publish it even if it is bad.* If tracking error turns out to be large for every realistic
counterparty, the correct conclusion is that the cog belongs in a narrower class of contract
than §4 claims — and finding that out is worth more than another specification section.

---

## What is explicitly not on this list

- **More whitepaper sections.** The argument is in better shape than the evidence. Writing is
  no longer the constraint.
- **Splitting COG-1 into classes** (text / reasoning / vision / private / low-latency). The
  outside review is right that one price cannot represent all workloads, but building five
  indexes before one has ever produced a receipted fix multiplies the unvalidated surface.
  Revisit after Phase 1.
- **x402 / AP2 upstream standardisation.** The denomination extension is a reference emitter
  with golden fixtures, deliberately. Nobody standardises a denomination for an index that has
  never published a settleable number.

---

## Summary

| Phase | Blocked on | Cost |
|---|---|---|
| 0 — exam calibration, endpoint identity, plumbing | nothing — **do it now** | **\$0** (house proxy) |
| 1 — the depth gate | a decision to spend | ~\$450 for 30 days |
| 2 — duration + a second publisher | Phase 1, then a relationship | operational |
| 3 — tracking study | counterparty cost data we do not have | a partner, not a budget |

Phase 0 is free, and its most valuable output is a *harder exam* — the proxy calibrates the
instrument even though it cannot sit COG's actual candidates. Phase 1 is the milestone that
changes what this project *is*: until one depth-gated buy has run, "depth-verified" is a plan,
not a property. Everything after that depends on a second party caring, which is earned rather
than built.

**The honest one-line status:** the specification and the contracting layer are in good shape;
the evidence behind the number is not, and no amount of further writing changes that.

---

Licensed CC BY 4.0, like the rest of the prose here. See [`LICENSE-DOCS`](LICENSE-DOCS).
