# COG — Governance of the Index

*Draft 0.1 — July 2026 — ProofOfWorks*

## Why this file exists

A cryptographic signature proves **who published a number**. It does not prove that the
methodology was neutral, that the observations represented the market, or that the publisher
had no stake in the result. The moment a third party uses the cog fix to compute a real
payment, the entity that publishes it stops being a researcher and becomes a **benchmark
administrator** — a position of financial power over parties who did not choose it.

Everything in this repository up to now has been about making the number *verifiable*. This
file is about constraining the *discretion* that surrounds it. They are different problems and
receipts do not solve the second one.

## The conflict, stated plainly

As of this draft, one organisation — ProofOfWorks — does all of the following:

- selects which models are allowlisted,
- writes and scores the qualifying exam that decides which models are eligible,
- buys the inference that produces the receipts,
- computes the fix,
- holds the only signing key,
- publishes the result,
- **and wrote both sides of the worked example contract**, using two keypairs it generated and
  controlled itself.

That is not a neutral benchmark. It is a reference implementation operated by an interested
party, and no procurement or legal team should treat it as anything else today. The demo
signatures in [`contracts/examples/`](contracts/examples/) demonstrate that the *verification
machinery* works; they demonstrate nothing whatsoever about independent adoption, and the
README says so.

We would rather write that down than have a counterparty discover it.

## What the administrator can actually move

These are the discretionary levers. Each one is a place where a publisher could, deliberately
or not, move somebody's invoice:

| Lever | Why it matters |
|---|---|
| Model allowlist | Admitting or excluding an endpoint moves the median directly |
| Exam contents and threshold | Decides eligibility; a private set is unauditable by design |
| Fix window and smoothing | Changes which observations count |
| Data exclusions / outlier handling | The classic benchmark-manipulation surface |
| Endpoint identity decisions | Whether a realiased model is "the same model" |
| Corrections and restatements | Retroactively changes settled invoices |
| Methodology changes | Changes the unit under live contracts |
| Fallback activation | Decides when the ladder drops a rung |
| Signer keys | Whoever holds them *is* the index |

## Commitments

These bind any fix published from this repository. They are deliberately narrow: we would
rather commit to a few things we will actually do than publish an aspirational charter.

**1. Methodology changes are announced before they take effect.** No change to the basket,
allowlist, blend, window, or fix rule applies to a fix published before the change was public.
Spec files are content-hashed in [`spec/SPEC-HASHES.json`](spec/SPEC-HASHES.json) precisely so
a contract can pin the methodology it agreed to and detect a silent edit.

**2. Corrections are bounded and never silent.** A published fix may be restated only within a
declared correction window, and only by publishing a *new* signed record that references the
superseded one. The original is never deleted or edited in place. Contracts set their own
tolerance via `correction_window_days`; a fix restated after a party has settled against it is
a dispute, not an administrative action.

**3. The archive is append-only.** Dated archive entries and their signatures are never
rewritten. If we get one wrong, the wrong one stays, with a correction next to it.

**4. Errors are published as prominently as claims.** Two are already in this repository: the
withdrawn OS-sandbox soundness claim, and the "volume-weighted median" label that credited a
weighting no-op with a security property it never had (see `WHITEPAPER.md` §3). Both are
documented in place rather than quietly edited out. That is the standard.

**5. Refuse rather than guess.** The fixer exits non-zero rather than publish below its
resolved-model floor or below three qualifying models. A missing number is recoverable; a
confidently wrong one that settles an invoice is not.

**6. Fallback rungs are labelled and the weak ones cannot settle.** The `external-anchor` and
`bundled-snapshot` rungs are never settleable, and `min_tier` in the CDO lets a counterparty
refuse the weaker rungs entirely. Evidence quality is on the face of every invoice.

**7. Conflicts are disclosed.** If ProofOfWorks ever holds a position that a cog fix would
settle — as a party to a cog-denominated contract, or any other exposure — that must be
disclosed in this file before the fix is relied upon. At the time of writing there is none,
because there are no live contracts.

## What is missing (and what would have to be true)

We do not meet the governance standard that
[IOSCO's Principles for Financial Benchmarks](https://www.iosco.org/library/pubdocs/pdf/ioscopd415.pdf)
sets for a benchmark that determines material payments. The cog is probably not *in scope* for
financial-benchmark regulation today, but the expectations become relevant the moment third
parties rely on it, and the honest position is to measure ourselves against them early rather
than argue about jurisdiction later.

Unmet, in rough order of how much each one matters:

- **No independent publisher.** One organisation, one key. The `publishers[]` array and
  `multi_publisher_rule` (`priority-order` / `median` / `quorum-median`) exist in the CDO schema
  so a contract can name several and take a cross-publisher median — but today there is only
  one, so that machinery is untested in production. **A single-publisher index is a single
  point of both failure and capture.**
- **No external attestation of receipts.** Nobody but us has verified that the buys happened.
- **No formal oversight function.** No independent review of allowlist or exam decisions.
- **No appeal path for a disqualified provider.** A model that fails the exam has no recourse,
  and the exam is ours.
- **No key rotation or key-compromise procedure.** Signing keys are long-lived and there is no
  published revocation story.
- **No dispute procedure** beyond "recompute it yourself and show your working," which is
  necessary but not sufficient — it resolves arithmetic disputes, not judgement disputes.
- **No published tracking-error study.** See `WHITEPAPER.md` §6 on basis risk.

## Before you sign anything against this index

A counterparty should require, at minimum:

1. ~90 consecutive daily production fixes, published without gaps.
2. Populated receipt arrays — the depth gate actually exercised at spec size (K=5 × 10M tokens).
3. Endpoint pinning and model fingerprinting, so realiasing is detected rather than absorbed.
4. At least three independent publishers or witnesses, with independent keys.
5. A published operational report: disputes, corrections, tracking error, fallback activations.
6. `min_tier`, `collar`, and `correction_window_days` set deliberately in the obligation.

**None of items 1–5 is satisfied today.** Receipts are `[]`, the depth gate has never run at
spec size, and the published series is days long, not months. Until that changes, this is a
specification with a reference implementation — not an operating index, and not something to
denominate a material obligation in.

## Making the publisher replaceable

The most durable contribution here is probably the **contract schema, not our price series**.
A CDO names its publishers, pins the spec by hash, sets a minimum evidence tier, declares a
collar, and — via `on_publisher_cessation` — says what happens if the publisher stops
publishing: fall back to the next named publisher, convert the remaining cogs at the last
eligible fix, or reopen negotiation.

That is deliberate. A contract written against this schema should survive us going away, and a
better-run index should be able to compete for the same contracts without either party
rewriting the obligation. An index nobody can replace is an index nobody should sign.

---

Licensed CC BY 4.0, like the rest of the prose in this repository. See
[`LICENSE-DOCS`](LICENSE-DOCS).
