# DeliveryProof — Verdict

**Status:** Concept — working prototype, v0.10 (local, unpublished)
**Date:** 2026-07-27
**Method:** two-agent adversarial review (Claude Opus 5 + Codex, via ContextRelay),
each pass independent, findings admitted only with a runnable proof-of-concept.

ThinkTank concepts end in an honest call. This is it.

## What held

**The central invariant is real.** "No capture when `verdict.ok !== true`" survives
every attack either agent brought. It is enforced three times independently: the
decision is derived solely from `verdict.ok`, a redundant assert guards the capture
branch, and — the one that actually matters — the rails re-check it at the money
layer. A forged receipt handed directly to a rail, bypassing the engine entirely,
still cannot capture on a failing verdict. That third layer is the difference
between a claim and a property.

**The canonicalization is honest.** `protocol/canonical.mjs` emits RFC 8785 text
from a code-unit-sorted key list rather than round-tripping through a JS object,
because ECMAScript reorders integer-like keys and would silently break the
`RFC8785-JCS` claim. Most implementations ship that bug.

**The router cannot be lied to by verifiers.** Capability profiles are declared by
the protocol, not self-advertised. Security-significant predicate kinds cannot be
routed around by a permissive policy. The router throws rather than downgrade.

**Failure modes point the right way.** Delivery and verification exceptions become
negative verdicts and refunds rather than crashes with money held.

## What didn't — and what it cost to find

Two headline claims held *inside* `settle()` but were not enforced at the
boundaries. Both took an executable exploit to establish, and both were found by
adversarial review rather than by reading the code:

1. **Rails authenticated nothing by default.** Through v0.9.1, a rail built
   without a `settlementPublicKey` verified no signature at all. A receipt with
   `verdict.ok: true`, `decision: 'release'` and correct binding fields captured a
   held escrow with no settlement private key involved. Both agents reproduced it
   independently. Partially disclosed in the README, and listed as a follow-up in
   the prior review — but shipped as the default, which is what made it real.

2. **The engine signed assurance claims it never checked.** `settle()` verified
   only that `routeDecision.selected` matched the verifier's name, then signed the
   caller's own `selectedAssurance`; `assertReceiptMeetsPolicy()` then trusted that
   signed number. An assurance-1 `schema` verifier satisfied a `minAssurance: 3`
   policy via a hand-written `selectedAssurance: 99`. This one was *not* disclosed
   anywhere, and it defeated the project's actual differentiator — the
   no-silent-downgrade router — rather than a peripheral default.

Both are closed in v0.10, with regression tests derived from the PoCs.

**Then the fixes were attacked, and that round found something worse.** The
contract object handed to `rail.authorize()` was the *same mutable object* later
handed to seller-controlled `produceEvidence()` and then to the verifier. A
malicious seller mutated the predicate mid-flight — `sum([100])` became
`sum([1,2])` — returned the weakened answer, and the genuine verifier passed it
while `contractHash` still committed to the original terms. Funds captured, receipt
signature valid, receipt attesting to terms nobody had verified. That defect
predates v0.10 entirely and neither first-round pass found it.

The same round also found that a custom verifier could inherit a built-in's
assurance by reusing its name, that a `routeDecision` getter could show one value
to validation and another to the policy check, that `createdAt: 0` silently
disabled SLA enforcement, and that prototype pollution could make a rail verify
against an attacker-supplied key. All closed, all with regression tests.

**The lesson worth keeping:** every one of these is the same failure. Signed ≠
checked. Binding a claim into a signed receipt makes tampering *evident*; it does
nothing about a claim that was false, or a term that changed, before signing. A
verification system is exactly as good as the weakest thing it neglects to
re-derive — and the thing it neglects is rarely the thing it documents.

**The second lesson:** the review that found the most severe defect was the review
*of the fixes*, not the review of the original code. Fix rounds deserve the same
adversarial pressure as the code they fix, and neither round would have found
these by reading alone — every finding here required a running exploit.

## What it's worth

The escrow shell was never the hard part, and this repository proves it by being
small. The contribution is the content-level delivery predicate and the
same-bytes demonstration — shallow verifier releases, deep verifier refunds, on
identical delivered bytes. That artifact is the thing worth keeping.

The prior review scored innovation at ~26% against TessPay (arXiv, Feb 2026) and
FairSwap/OptiSwap (CCS 2018). Nothing in this pass moves that number. What this
pass changes is confidence in the *implementation*: the invariant is genuinely
layered, and it survived everything thrown at it. The defects were elsewhere —
mostly at the boundaries, though the worst one (a mutable contract handed to
seller code) was in the core path and had been there since well before v0.10.

## Trust roots no amount of code closes

Naming these is the point of the exercise. None are bugs; all are load-bearing.

- **The predicate author.** The verifier is injected. `settle()` guarantees capture
  iff `verdict.ok` — never that the verdict is *correct*. A weak or dishonest
  verifier releases money entirely legitimately. A perfect proof against the wrong
  predicate is still wrong.
- **Custody of the settlement key.** Signature verification proves the configured
  settlement authority signed a receipt. It says nothing about whether that
  authority's verifier was honest, or whether its key or call surface was
  compromised.
- **The verifier registry.** An operator who registers a weak verifier can route
  contracts to it. The engine now refuses to *sign a protocol assurance level* for
  anything that is not the built-in object by identity — so a weak verifier can no
  longer inherit `dataset`'s assurance by taking its name — but it cannot judge a
  custom verifier's quality. Registry composition remains an operator
  responsibility.

  (This one is here because the first draft of this verdict listed name-collision
  as unfixable. That was wrong: object identity fixes it, and the adversarial pass
  said so. Recorded because the reflex to file something as an immutable trust
  root, rather than a defect, is itself a failure mode.)
- **`builtin-replay` is four operations.** `sort`, `sum`, `unique`, `reverse`.
  Recomputing those is genuinely deep for the predicates they cover — the verifier
  was renamed rather than downgraded for exactly that reason — but it is not
  general re-execution and must not be read as such.
- **Tier B proves provenance, not truth.** `signed-oracle` proves an allowed
  attester signed a bound statement. Whether the statement is true is outside the
  system.
- **Finality and custody remain operator-owned.** No adapter here makes an
  exactly-once, reorg-safe, or custody guarantee.

## What to stop doing

- **Stop shipping security-critical behaviour as opt-in.** Both v0.10 P0 findings
  reduce to the same root cause. If a check is the one that distinguishes a real
  settlement from a forgery, the safe configuration is the default and the unsafe
  one gets a blunt name (`allowUnsignedReceipts`).
- **Stop treating "bound into the signed receipt" as a security property on its
  own.** It is an integrity property. Re-derive every claim from a trusted source
  before signing it.
- **Do not build the general re-execution sandbox.** It needs an execution format,
  hermetic inputs, a deterministic runtime, syscall/network/fs policy, and real
  containment. That is a different project with a far worse risk profile, and
  half-building it would be the least honest thing this repository could do.
- **Do not claim production readiness on the strength of a green suite.** The suite
  was green before every one of these findings, too. Tests encode the failures you already thought of.

## Open

- No third-party audit. Two AI agents adversarially reviewing each other is a
  stronger signal than one pass, and weaker than a human security audit.
- `keyId` widening (DER-based, 128-bit) still deferred.
- The cross-process replay store ships (`createSqliteReplayStore`), but no
  deployment has exercised it under real concurrent load.
- Recovery story for a rail backend failure *after* the receipt is signed is
  documented, not automated: that window still leaves a held terminalization gap.
