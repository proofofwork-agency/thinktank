# DeliveryProof — Dual-Agent Review, Rating & Hardening Report

**Date:** 2026-06-02   **Subject:** `deliveryproof` v0.9.0
**Reviewers:** Claude (Opus 4.8) + Codex (OpenAI), coordinated via ContextRelay
**Method:** two-agent cross-validation — each domain (code, landscape) was analyzed
*independently* by both agents, then cross-referenced. Findings below are reported
as **agreed** (both passes converged) or **single-source** where noted.

---

## 1. Executive summary

DeliveryProof is a **well-engineered, unusually honest reference implementation** of
an idea whose core is **already in the water in mid-2026**. It correctly identifies a
real gap — agent-payment rails verify *authorization*, not *delivery* — and fills it
with a deterministic, objectively-recomputable content predicate that gates
release/refund.

- **Innovation: ~26%** (incremental-but-real). The novelty is in *execution* —
  content-level predicates, the runnable "shallow-releases / deep-refunds on the same
  bytes" demo, the Tier-A/B/C taxonomy, and shipped standards-projection — **not** in
  the concept, which has a contemporaneous published twin (TessPay) and decades-old
  academic precedent (FairSwap/OptiSwap). *Both agents converged on "narrow novelty".*
- **Code: solid core, fail-open edges — now fixed.** The central money-safety
  invariant ("no capture when `verdict.ok !== true`") **holds inside `settle()`**
  (both agents drove ~10 hostile verdict shapes through it; all refunded). The real
  risks were **exported, money-moving surfaces that failed *open* by default** (rails,
  interop) plus a **canonicalization bug** that silently broke the "RFC8785-JCS" claim.
- **All actionable findings fixed tonight.** Test suite **251 → 260, all green**.
  8/8 (Claude) + 5/5 (Codex) independent vuln-closure probes pass. Committed to branch
  `hardening/v0.9-review-fixes` (commit `dc19f8a`); `main` untouched, not pushed.
- **Audit grade: B- → A-** after this pass (per the independent code-audit), with two
  documented follow-ups remaining (mandatory-signature default; keyId widening).

---

## 2. Innovation score: ~26%

**What fraction of the value proposition is novel vs assembled from existing art.**

| Component of the value prop | Closest prior art | Novel? |
|---|---|---|
| "Authorization ≠ delivery" gap diagnosis | Universally acknowledged (x402/AP2/Stripe ACP all disclaim fulfillment) | ❌ ~0% |
| Verify-then-pay / predicate-gated escrow (category) | **TessPay** (arXiv:2602.00213, Feb 2026) — near-identical tiered trust model, weeks earlier | ❌ ~0% |
| Bind settlement to content-correctness, refund on negative verdict | **FairSwap** (CCS 2018) + **OptiSwap** (2020) — on-chain, *with formal fairness guarantees* | ❌ low |
| Escrow/refund mechanics, signed receipts, Merkle, ERC projection | RFC 6962, certified-email NRR, EAS, standards by others | ❌ low |
| **Content-level predicate** (schema/hash/dataset/api/JSON-path) vs execution-attestation | TessPay/A402 gate on TEE/TLSNotary *execution*; ERC-8183/8004 leave predicate undefined | ✅ **high (narrow)** |
| **Runnable same-bytes demo** (shallow RELEASES / deep REFUNDS on identical bytes) | No surveyed project ships this contrast as a first-class artifact | ✅ **high** |
| Shipped, standards-projecting reference impl (ERC-8004/8183 + 260 tests) | TessPay is paper-only; ERC-8183 is a draft | ✅ medium |

**Why 26% and not higher:** the single most load-bearing claim (predicate-gated,
content-level, tiered verify-then-pay) is independently published by TessPay weeks
earlier and academically precedented by FairSwap, so it cannot earn category-defining
credit. **Why not lower (~15%):** the content-first orientation, the same-bytes
demonstration artifact, and being shipped/working/standards-projecting are genuinely
under-served and real.

> **Cross-validation:** Codex's independent landscape pass reached the same place —
> *"the basic 'escrow releases after evaluator/proof' pattern exists; DeliveryProof's
> defensible angle looks narrower: a portable receipt/verifier library focused on
> artifact-level predicates rather than a new payment rail."* Two independent passes,
> same conclusion.

---

## 3. Rating vs the landscape — the good / bad / ugly (market view)

The 2026 field splits cleanly, and DeliveryProof targets the half the big rails skip:

- **Mature rails (verify payment, NOT delivery):** x402 (live — ~69k agents, ~$50M+
  vol), Google AP2 (60+ partners), L402, Skyfire/KYAPay, Stripe+OpenAI ACP, Stripe MPP.
- **Escrow+evaluator (gate on a verdict, but predicate is abstract/subjective/shallow):**
  Virtuals ACP (live on Base, LLM-evaluator), ERC-8183 (draft, predicate undefined),
  Masumi (Cardano), and the x402 verify-before-release cluster PayCrow / KAMIYO /
  Settld (gate on HTTP-200 + JSON-schema = exactly the *shallow* case DeliveryProof
  targets).

**Verdict:** *differently-positioned* — slightly **behind** the best alternatives on
*rigor* (FairSwap/OptiSwap have formal fairness; TessPay published first), **ahead** on
*shipped concreteness + honesty*. A credible "deep evaluator layer," **not** a
category-definer, **not** a deployable product.

### ✅ The Good
- Problem diagnosis is real and validated across six independent web sweeps.
- Exceptional intellectual honesty: "not trustless, names the trust points," "pure
  projection — no contracts/wallet/chain," explicit "What This Is Not," Tier A/B/C.
- Content-first predicate is the correct under-served axis — orthogonal to and
  composable with zkTLS/TEE/oracle stacks (which prove provenance, not content).
- Disciplined crypto hygiene (RFC 6962 domain separation, CVE-2012-2459 avoidance,
  partial-Merkle *fails closed* on completeness claims).
- Genuinely runnable: 260 tests + 11 demos exercising the real flows.
- Well-positioned interop: ships the concrete evaluator that ERC-8004/8183 leave abstract.

### ⚠️ The Bad
- The most load-bearing claim isn't novel (TessPay; FairSwap/OptiSwap).
- **Whitepaper cites the wrong canonical theorem** — it grounds itself in a self-derived
  double-spend / *money* trilemma; the *fair-exchange* impossibility that actually
  governs "pay-iff-delivered" (Pagnia-Gärtner 1999, EGL 1985, Cleve 1986) is absent.
- The verifier is an inline/online TTP — the *least* trust-minimized point on the
  established spectrum — while the framing implies strong trust reduction.
- Not deployed / not custody; every live competitor settles real value today.

### 🔴 The Ugly
- The foundational citation is arguably **mis-grounded** (a money-impossibility result
  used to justify a fair-exchange problem), which undercuts theoretical credibility on
  the exact axis the paper leans on — while the on-point literature (which both
  *validates* the design and partly *scoops* it via FairSwap) is the one missing.
- Risk the headline collapses to **"TessPay's idea, but shipped."** *Open item:* the
  close TessPay tier-correspondence came from a single un-verified fetch — **read the
  TessPay PDF directly** to settle this.

---

## 4. Code analysis — the good / bad / ugly (engineering view)

### Central invariant: **HOLDS in the engine; was fail-open at the boundary**
Both passes independently confirmed the single `rail.capture()` call site
(`engine/deliveryproof.mjs:234`) is reachable only through the `decision==='release'`
branch **and** a second `verdict.ok !== true` throw-guard; `decision` is derived from
`verdict.ok` only after `assertVerdict()` forces a boolean. ~10 hostile verdict shapes
(`ok = 1`, `"true"`, `{}`, `[]`, `new Boolean(true)`, `null`, getter-flips, verifier
throws/async-rejects) all produced `decision:'refund'`. **The orchestrated path was
never the problem.** The problem was the *exported* rail/interop seams the docs market
as the production integration points.

### Findings (cross-referenced; both code passes + the audit)

| # | Severity | Area | Issue | Status |
|---|---|---|---|---|
| 1 | **Med→Crit** | `canonical.mjs` | "RFC8785-JCS" false for integer-like keys (`{"10":1,"2":2}` mis-ordered); breaks cross-impl hash/signature/Merkle | ✅ **FIXED** |
| 2 | **Med→Crit** | rails (escrow-mock, durable) | Fail-open: forged `release`+`verdict.ok=false` captures on a keyless rail | ✅ **FIXED** |
| 3 | **High** | interop (erc8004/8183) | Projects contradictory/unsigned receipt to chain-facing `complete`/`100` | ✅ **FIXED** (consistency gate) |
| 4 | **High** | `rail-conformance` | Suite gave adapters a green check while shipping the fail-open footgun | ✅ **FIXED** (new case) |
| 5 | **Med** | nonce-registry WAL | Lone/forged `mark` record synthesizes replay state after restart | ✅ **FIXED** |
| 6 | **Med** | verifiers (schema, api-response) | Standalone verifiers accept non-finite `Infinity`/`NaN` | ✅ **FIXED** |
| 7 | **Low/Med** | `schema.mjs` | Amounts allow negative/zero/non-finite (money-as-float) | ✅ **FIXED** (positive-finite) |
| 8 | **Low/Nit** | `crypto.mjs` keyId | 64-bit prefix over PEM text (format-sensitive) | ⏸️ **Deferred** (documented) |

> **Severity reconciliation:** Codex graded the canonicalization bug MEDIUM; Claude's
> audit graded it CRITICAL. Reconciled: it is a **silent cross-implementation
> correctness break** (a second-language JCS verifier computes different hashes for the
> same logical object), **not** an in-process collision or money exploit — high impact
> for interoperability, no in-process exploit. Either way: fixed.

**Sound areas (agreed):** receipt signature field coverage, keyring-confusion defense,
Merkle leaf/node domain separation + partial-sample scoping, router no-silent-downgrade,
testsuite worker (deterministic, not a hostile sandbox — and the docs say so), number /
string / unicode / prototype handling in canonicalization.

---

## 5. What was fixed tonight (+ verification)

All fixes are in `src/`; regression tests added; **suite 251 → 260, all green.**

1. **`protocol/canonical.mjs`** — rewrote the serializer to emit JCS text directly from
   the code-unit-sorted key list (no JS-object round-trip that JS re-orders). The
   `CANONICALIZATION='RFC8785-JCS'` claim is now actually true; string-keyed records and
   arrays remain byte-identical.
2. **`rails/escrow-mock.mjs` + `durable-rail.mjs`** — enforce `decision ↔ verdict.ok`
   consistency before *any* terminalization (so "no capture on `verdict.ok!==true`"
   holds at the money layer, not just in `settle()`); added opt-in `requireSignature`
   fail-closed mode for production.
3. **`interop/erc8004.mjs` + `erc8183.mjs`** — refuse to project an internally
   contradictory receipt into a chain-facing success.
4. **`engine/nonce-registry.mjs`** — WAL `apply()` validates record fields and rejects a
   lone/forged `mark` (mark-before-reserve / fingerprint mismatch).
5. **`verifiers/schema.mjs` + `api-response.mjs`** — reject non-finite `Infinity`/`NaN`.
6. **`protocol/schema.mjs`** — contract & receipt amounts must be positive and finite.
7. **Tests** — new `test/hardening.test.mjs` (9 regressions) + a new rail-conformance
   case `no-capture-on-contradictory-verdict`.

**Verification:**
- `npm test` → **260 / 260 pass** (was 251).
- `npm run check` (node --check, all `.mjs`) → clean.
- Demos (production-seams, keccak-interop, dataset money-shot) → run end-to-end.
- **Claude probes: 8/8** vuln-closure (incl. legitimate paths still work).
- **Codex independent probes: 5/5** — *"All five direct probes are closed in the current tree."*
- **Commit:** `dc19f8a` on `hardening/v0.9-review-fixes` (`main` untouched, not pushed).

---

## 6. Recommendations / follow-ups (NOT done tonight)

1. **Make rail/interop signature verification mandatory by default** in a future major
   (thread the settlement public key into rail construction). The consistency check
   closes the *contradictory*-receipt hole; only signatures close the *forged-but-
   consistent unsigned* receipt hole. `requireSignature` is shipped as opt-in now.
2. **keyId** — derive from canonical SPKI DER (PEM-format-stable) and widen to 128-bit;
   deferred tonight because it churns golden signed-receipt fixtures.
3. **Whitepaper** — cite the actual fair-exchange impossibility line (Pagnia-Gärtner,
   EGL, Cleve), engage FairSwap/OptiSwap, and soften the novelty framing to match the
   honest body.
4. **Verify the TessPay PDF directly** — the single highest-leverage open item for the
   novelty claim.
5. **Amounts** — consider positive-integer minor units or decimal-string-with-exponent
   for real money handling.

---

## 7. Methodology

This used a **two-agent cross-validation** design over ContextRelay: Phase 1 — Codex did
code analysis while Claude did landscape research; Phase 2 — they swapped; Phase 3 —
Claude cross-referenced both independent passes and (per delegated authority) drove the
hardening pass, with Codex as independent verifier. Convergence between two independent
agents (on the invariant, the JCS bug, the fail-open boundary, and the narrow-novelty
verdict) is the basis for the confidence levels above; divergences (e.g. JCS severity)
are reconciled inline.

*Prepared autonomously overnight under the human's "full control to finish it" delegation.*
