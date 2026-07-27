# vouch

**Permissionless surety for machine work.** Anyone can underwrite anyone else's
promise, and settlement is a deterministic verifier over a receipt — never a
claims process, never a vote.

```
node examples/demo-deliveryproof.mjs   # the money shot
node --test test/*.test.mjs            # the adversarial proofs
```

---

## The era this belongs to

Every crypto era removed exactly one gatekeeper:

| Era | Gatekeeper removed |
| --- | --- |
| Layer 1 | settlement |
| Layer 2 | throughput and cost |
| Layer 0 / LayerZero | interop and messaging |
| DEXes | listing and exchange |
| Stablecoins | the unit of account |
| pump.fun | asset creation and instant liquidity |

The one still standing in 2026 is **the right to make a credible promise.**

Millions of AI agents now sell work. Any of them can *claim* anything, and a new
agent has only two ways to be believed: rent reputation from a platform that
gates it, or post its own capital — which a new agent by definition does not
have. Credibility is still issued by incumbents: marketplaces, rating systems,
app stores, insurers.

vouch removes that gatekeeper. A stranger's capital can stand behind an unknown
agent, and the price that stranger charges *is* the market's live probability
that the agent delivers.

## Why this is not `deliveryproof`

They are adjacent layers, and vouch **consumes** DeliveryProof rather than
competing with it.

DeliveryProof answers *"did it happen?"* It holds the buyer's own fee in escrow
and releases or refunds it against a machine-checkable predicate. Its own README
is precise about the limit: it "makes trust explicit and checkable; it does not
abolish trust."

vouch answers *"who eats the loss, and what does that risk cost?"*

The gap is concrete. A buyer pays **4 USDC** for a market signal and trades
**5,000 USDC** on the answer. The agent returns schema-valid but wrong data.
DeliveryProof works perfectly — the deep verifier catches it and refunds the
4 USDC fee.

The buyer is still out **4,996 USDC**.

No escrow protocol can close that, because escrow only ever holds the fee.
Closing it requires *someone else's* capital, committed before the work and
priced. That is vouch.

Two more differences follow from it:

- **DeliveryProof cannot make a trade happen that otherwise would not.** It
  requires the buyer to already trust the agent enough to engage. vouch lets a
  third party's balance sheet substitute for that trust.
- **DeliveryProof produces no price.** Nobody is at risk, so nothing is quoted.
  In vouch a third party is at risk, so a price exists — and that price is the
  most valuable output of the system.

DeliveryProof's signed refund receipt **is** the trigger vouch settles on. Bill
of lading, then marine insurance. Shipping needed both.

> The composition is *injected*, never imported (`createDeliveryProofAdapter(dp)`),
> so vouch has zero dependencies and does not break when DeliveryProof changes.
> `demo-deliveryproof.mjs` exits cleanly with an explanation if it is absent.

## What layer does this run on?

**None. That is deliberate.** Stablecoins were not a layer either.

vouch is a **sidecar on the agent layer — MCP** — because that is where 2026's
economic actors already live and already advertise themselves. There is no chain
to deploy, no token to launch, no validator set. An agent attaches one MCP server
and has a score. Settlement is rail-neutral: the ledger here is local and
hash-chained, and any escrow or chain can be plugged in underneath without the
market logic changing.

The entire package is Node built-ins. It runs offline.

## Does it need a chain?

It needs somewhere to hold money atomically. That is not the same as needing a
chain, and definitely not a new one.

**Needs a settlement venue:** custody of the underwriter's locked collateral;
payout and subrogation happening atomically or not at all; a global view so the
same collateral cannot back two policies.

**Needs no chain, by construction:** the verifier (deterministic over delivered
bytes — anyone re-runs it and gets the same answer), the oracle (a pure fold
over the log), the badge (verified by recomputation), and the pricing (it is a
market; underwriters quote what they like).

That split is the architectural payoff. Most on-chain insurance *needs* a chain
because claims are settled by **voting**, so consensus over a subjective
judgement is unavoidable. vouch has no adjudication step. There is nothing to
reach consensus about. Only the money-holding is left.

Three deployments, none of them a new chain:

| | Custody | Trade-off |
| --- | --- | --- |
| **Operator** | one custodian holds the float | fastest to a real pilot; you trust the operator |
| **Existing rails** | reuse DeliveryProof's `authorize/capture/refund/status` seam — it already maps to x402, Stripe manual-capture, AP2, card auth | no new infrastructure; not permissionless |
| **Contract** | escrow-and-lock on an existing chain | permissionless entry, no operator risk; ~200 lines, gas per policy |

**Known gap:** `protocol.mjs` holds accounts in an in-memory `Map`. The design
is rail-neutral in spirit but *not yet in code* — there is no pluggable custody
seam the way DeliveryProof has one. Extracting `deposit / lock / unlock /
payFromLocked / transfer` behind that interface is the single change that takes
this from "concept" to "could run somewhere", and it does not touch the
economics.

## Regulatory posture

Not legal advice; specific thresholds need a lawyer. But the structural read
matters enough to record, because it changed the default configuration.

**MiCA is probably not the binding constraint — insurance law is.** MiCA
excludes insurance products from scope. And vouch has every hallmark of an
insurance contract: a premium, an uncertain event, risk transferred to a third
party, and payout capped at demonstrated loss. That last one is decisive —
indemnity plus subrogation plus insurable interest is the textbook definition of
*suretyship*, which is its own named class of non-life insurance under Solvency
II.

The uncomfortable irony: **the features added to defeat collusion are exactly
what pull it into insurance regulation.** A version that paid out on failure
regardless of real loss would be a wager — a derivative or gambling product,
a different and also-bad regime. Making it indemnity-based to kill the collusion
attack made it legally a surety bond.

**Where MiCA does bite:** holding collateral or premiums in crypto on behalf of
users is custody, a licensed CASP activity — the most likely hook. Collateral
denominated in a stablecoin means using an e-money token. And tokenising the
policy so it trades likely lands in MiFID II as a derivative, which is worse,
not better. The realistic bad outcome is being hit by both regimes at once.

**"It's just a smart contract" only goes so far.** Regulation attaches to
persons carrying on an activity, not to code. An immutable contract with no
admin key and no fee switch is genuinely hard to license — but each participant
is separately regulated, so an underwriter systematically writing cover for
premium is carrying on insurance business regardless of the plumbing.
Permissionlessness does not remove that liability, it distributes it onto users.
In practice regulators find someone: the deployer, the front-end, the docs site,
whoever takes a fee or holds an upgrade key.

**The deeper business problem:** insurance is a promise to pay later, so its
whole value is the creditworthiness of the payer. Permissionless underwriting
self-selects for anonymous, thinly-capitalised counterparties — the least
credible payers — while regulated underwriters with real balance sheets cannot
participate unlicensed. That tension has killed most on-chain insurance.

vouch's answer is that **coverage is pre-funded and locked before the policy
binds.** Solvency is verifiable rather than promised. Prudential insurance
regulation exists largely to ensure the insurer can actually pay; if cover is
fully collateralised, that concern is substantially answered by construction.
That is a strong argument, not a safe harbour — no regulator has blessed it.

### Why the default is fully collateralised

Three independent lines of reasoning converge on one design decision:

| Lens | Conclusion |
| --- | --- |
| **Economic** | collusion is only provably unprofitable when coverage ≤ bond |
| **Legal** | fully bonded and subrogated is the weakest candidate for third-party risk transfer |
| **Prudential** | pre-funded cover answers the solvency question by construction |

An economist, a lawyer and a regulator reach the same place from three different
directions. So `createVouchMarket()` **refuses cover beyond the promisor's bond
by default**; the `reputational` regime requires `allowReputational: true` and
carries the collusion exposure the tests demonstrate.

The cost is real and worth naming: **no leverage.** An underwriter can only
cover what it has locked. That is narrower and duller than the permissionless
dream, and it is the version that survives all three lenses.

## How it self-promotes

The distribution strategy is the mechanism, not a marketing plan:

1. An agent gets vouched and receives a **badge** — a live, collateral-backed
   delivery score.
2. The badge wins work, so the agent displays it: README, listing, MCP manifest.
3. Every buyer who sees it learns what a vouch score is.
4. Buyers start *expecting* one. Agents without cover start seeking it.
5. More settled history sharpens the oracle, which lowers premiums for good
   agents, which increases the incentive to display.

The same loop that made TLS padlocks and "Powered by Stripe" ubiquitous — with
one difference. **The badge cannot be self-awarded.** The number in it is
derived from capital actually put at risk and outcomes actually settled, and
`verifyBadge()` recomputes it from the ledger. Forging one is not hard, it is
pointless.

```js
mintBadge(market.ledger, 'signal-agent')
// **vouched 97.2%** (vouched) — 199 delivered / 2 failed · cover costs 307 bps
```

`renderBadgeSVG` emits a self-contained SVG — no CDN, no fetch, no tracking.

## The mechanism

Three rules carry all the economic weight.

**1. Indemnity, not wager.** A payout is capped at the loss declared *ex ante*
and paid for, minus whatever escrow already returned. You cannot profit from a
failure, only be made whole. Over-insurance is refused at quote time. Declaring
exposure before the work — and paying premium proportional to it — is what stops
"value the loss once you know you're collecting."

**2. Subrogation.** When the underwriter pays, it acquires the beneficiary's
claim against the promisor and recovers from the promisor's bond. This is the
rule that makes deliberate failure expensive rather than free.

**3. No rehypothecation.** Locked collateral is locked. An underwriter cannot
pledge the same capital behind two promises, so headline coverage is always
backed by capital that exists.

And one rule the adversarial review forced, which turned out to be load-bearing:

**4. Reputation is only earned where capital was at risk.** Only outcomes with a
bound policy enter the oracle. Without this, an agent mints a spotless record
from free self-dealt jobs and buys cheap cover on the strength of it — measured
at a 98.1% score for zero cost before the fix. It also closes the mirror attack,
since you cannot grief a rival with fake failures nobody underwrote.

### The collusion result

Naive indemnity is exploitable: a colluding buyer and seller would net
`exposure − fee − premium`. Subrogation is what fixes it, and the fix is exact:

> **When coverage ≤ the promisor's bond, collusion is strictly unprofitable.**
> The colluding pair ends down exactly the premium they paid.

This is asserted numerically in `test/attacks.test.mjs`, not argued in prose.

Above that line the protocol does **not** claim collusion-resistance. Coverage
exceeding the bond is labelled `reputational`, and the test suite proves that
regime *is* exploitable — because a concept that hides its own failure mode is
worth nothing. `market.coverageRegime(id)` returns which regime you are in.

### The verifier is the load-bearing part

Settlement is a pure function from evidence to outcome, re-runnable by anyone
holding the same bytes. That is the line between vouch and every "decentralised
insurance" protocol whose claims are decided by token-holder governance —
slow, subjective, and capturable by whoever holds the most votes.

It also closes the reverse attack: a beneficiary cannot manufacture a false
failure to collect, because the verdict comes from a deterministic verifier over
the delivered artifact and anyone can re-run it.

## The emergent byproduct

AMMs were built to swap tokens and produced a **price oracle** as a side effect.

vouch is built to move risk and produces a **trust oracle**: a live,
collateral-backed probability that any given agent delivers. Nobody operates it.
It is a pure fold over settled outcomes — `replayOracle(ledger)` reconstructs it
identically for any third party holding the log.

The estimator is a Beta-Bernoulli posterior with a Jeffreys prior, and that
choice does real economic work. An agent with no history gets a *wide*
posterior, so the conservative quote an underwriter prices off is expensive.
New agents are not assumed guilty, they are assumed **unknown**, and the cost of
being unknown is exactly the cost of the uncertainty. Adverse selection is
*priced out* rather than detected.

From the demo, after one failure on a 200-job record:

```
score        98.04%  →  97.21%
cover cost   107.71  →  153.33 USDC   (+42%)
```

Nobody adjudicated that.

## What the review council found

Built by a four-agent workflow: OpenCode coordinating, Claude as lead builder,
Codex and Grok as researchers. Their findings are recorded here including the
ones that went against the build, because a concept doc that only records
agreement is marketing.

### Grok (prior art): **DERIVATIVE**

> "vouch is surety + parametric insurance, re-skinned for machine-checkable
> agent jobs. Indemnity caps, subrogation, locked collateral and 'no wager' are
> not inventions; they are insurance law."

This is the strongest objection on the table and it is substantially correct.
Nothing in the risk mechanics is new — surety bonds are Roman, subrogation is
19th-century marine insurance, and Beta-Bernoulli experience rating is standard
actuarial credibility. Etherisc already does parametric payout on an objective
trigger.

What Grok allowed survives is narrow and worth stating precisely: the explicit
**coverage ≤ bond collusion bound**, composed with **fee-escrow residual loss**,
labelled `collateralized` vs `reputational`. Grok classes that as product design
rather than a new risk primitive. That is a fair reading. The honest claim for
vouch is therefore *not* "new financial mechanism" — it is **surety made
permissionless and settled without an adjudicator, for a class of promise that
could not previously be underwritten at all because nobody could verify it
cheaply.** Whether that is "innovative" or "a good port" is a real argument, not
a settled one.

### OpenCode (coordination): **REWORK**, and one call was overruled

OpenCode rated complexity 6/10 against a "simple" mandate and recommended
cutting the bond and subrogation entirely, on the grounds that the volume lives
in the `reputational` regime anyway.

**Overruled**, because Grok independently identified that exact mechanism as the
only thing that is not derivative, and because the demo shows an unknown agent
is uninsurable on someone else's capital — bonding is the *only* on-ramp. Cutting
it would leave new agents with no path in at all. Two researchers reaching
opposite conclusions is the reason to run more than one.

Its accepted findings:

- **The viral loop is weaker than the analogies suggest.** TLS padlocks and
  "Powered by Stripe" are free to display; a vouch badge costs locked capital
  and a recurring premium. That is a strictly harder cold start, and the loop
  above understates it. Fixing it needs a subsidised pilot, not better prose.
- **Go-to-market wedge:** signal-agents for small crypto trading desks. Fee
  $5–25 per call, consequential exposure $5k–50k per trade, premium 30–100 bps.
  The 1000× fee-to-exposure gap is exactly where escrow alone is insufficient.

### Codex (adversarial economics): **THEOREM BROKEN** — now fixed

Codex attacked the collusion proof and broke it four different ways. All are
fixed, each with a named regression test in `test/hardening.test.mjs`:

| # | Severity | Attack | Fix |
| --- | --- | --- | --- |
| 1 | critical | Premium of 0 makes the colluding pair end *flat*, not down — the theorem said "strictly" | premium must be positive |
| 1b | critical | `underwriter === promisor` collapses three roles into two; subrogation returns value to its source | promisor cannot underwrite itself |
| 2 | critical | Anyone could `open` a commitment naming a victim as promisor, then attest failure and confiscate their bond | `open` requires the promisor; `bind` requires the beneficiary |
| 3 | critical | `recovered` was a caller parameter — passing 0 on a fully refunded job manufactured a loss that did not exist | derived from the commitment, never the caller |
| 4 | critical | 100 free self-dealt jobs at `exposure=1` bought a 98% score and a cheap quote on 1,000,000 | only policy-backed outcomes count |
| 5 | high | A rival's score could be griefed with fake failing commitments | same fix, plus promisor authorization |
| 6 | high | A failed `bind` locked collateral before the premium transfer threw, stranding it with no policy to release it | preflight both legs, then move |

Finding 4 was the serious one: it falsified the headline claim that reputation
is collateral-backed. Reproduced before the fix, a free score of **9812** and a
premium of **20,790** on a million of exposure. The fix — *reputation is only
earned where capital was at risk* — is now the load-bearing rule behind the
badge, and it makes the concept's central claim true instead of aspirational.

**Not fixed (known, medium):** rounding dust. Premiums `ceil` upward, so 100
policies of exposure 1 cost more in aggregate than one policy of exposure 100.
Mitigated by a minimum policy size in production; not implemented here.

**Also unaddressed:** underwriter capital adequacy, reserving, and correlation
limits across policies — Grok's point that a real underwriter would demand them,
and that this design prices a single policy while saying nothing about a book of
them.

## Kill shot

The honest one: **most real-world losses are not machine-checkable.**

(A second, structural one now sits above: fully collateralised cover means no
leverage, so underwriting capacity is capped at locked capital. That is a much
smaller market than leveraged underwriting — and it is the price of the three
lenses agreeing.)

vouch only works where failure can be proved by a deterministic verifier over an
artifact. "The API returned the wrong city" qualifies. "The strategy was bad" or
"the code was subtly wrong in a way nobody specified" does not. The addressable
market is exactly as large as the set of promises someone can write a verifier
for — and no larger.

That set is growing fast in agent commerce, which is the bet. But if verifiable
work stays a niche, so does this.

A second: the `reputational` regime is where the volume would actually be —
unknown agents wanting cover they cannot bond — and it is collusion-exposed by
construction. It is now off by default rather than merely labelled, which is
more honest and also strictly smaller. Someone has to solve underwriting
uncollateralised agent risk eventually; this design does not.

## Layout

```
src/canonical.mjs    canonical JSON + domain-separated hashing
src/units.mjs        integer money; BigInt internals, Number surface
src/ledger.mjs       append-only hash-chained event log
src/commitment.mjs   the promise object
src/evidence.mjs     verifier adapters (incl. injected DeliveryProof)
src/protocol.mjs     the market + settlement engine
src/oracle.mjs       Beta-Bernoulli trust oracle
src/badge.mjs        the self-promotion artifact

test/attacks.test.mjs    the economic theorems
test/hardening.test.mjs  regressions for every broken attack above
test/core.test.mjs       encoding, ledger, money, oracle invariants
```

## Status

Concept complete: **35 tests**, two demos, one real composition with
DeliveryProof, zero dependencies, runs offline.

Known and deliberate gaps, in the order they would need closing:

1. **No custody seam.** Accounts live in an in-memory `Map`. Extracting them
   behind DeliveryProof's rail interface is what makes this deployable.
2. **Authorization is an `actor` argument, not a signature.** Honest for a local
   simulation; every `open`/`bind` check here becomes a signature check in
   production.
3. **Rounding dust.** Premiums `ceil` upward, so many small policies cost more
   in aggregate than one large one. Needs a minimum policy size.
4. **No portfolio view.** This prices a single policy and says nothing about a
   book: no reserving, no correlation limits, no aggregate exposure caps.
5. **No answer for a wrong verifier.** Settlement assumes the predicate is
   correct and well-defined. When it is neither, there is no recourse path.

It has never touched real money, a chain, or a counterparty. Do not point it at
any of them.
