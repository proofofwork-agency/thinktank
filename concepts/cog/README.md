# THE C⚙G

**A capability-indexed unit of account for the intelligence economy.**
Not a coin. Not a chain. A ruler that doesn't bend.

---

The price of cognition falls fast enough to break contracts: **~4.6× per year** at the
frontier tier on our own series (GPT-4-class inference: **$36.00 → $0.25 per million blended
tokens in 39 months** — 143×), and **~10× per year** at the commodity tier a16z measured
(MMLU~42: $60.00 → $0.06, 1,000× in 3 years). Every AI contract denominated in dollars is therefore
a hidden, unchosen bet on the rate of AI progress: fixed-price buyers are short it,
fixed-price sellers are long it. Result: nobody signs long-term AI contracts, and the agent
economy has no stable unit to write standing obligations in.

**The cog** fixes the ruler instead of the money:

> **1 cog** = the *depth-verified* market price, on the fix date, of running a frozen
> reference workload (1M blended tokens, 800k in / 200k out) on any model that passes a
> frozen capability basket (GPT-4-class tier) — a volume-weighted median of receipted,
> sized purchases, so a loss-leader sip can't set the fix.

Write the contract in cogs; settle in any currency at the daily published fix. Chile has run
its entire mortgage market this way since 1967 (the UF) — against *inflation of money*. The
cog is the same machine pointed at *deflation of intelligence*.

**What this project is actually for.** The measurement is largely solved and not by us: Epoch
AI already publishes an open, capability-normalized price series, and Ornn already publishes a
receipt-verified token index with far more money and distribution behind it. We consume the
first and do not race the second. What nobody has specified is how an **obligation** settles
against such a number — the settlement fix, what happens when publication fails, how a contract
survives the basket being replaced, and what unit an agent's standing mandate is denominated
in. x402 and AP2 now carry millions of recurring agent obligations, and every one of them
freezes a fiat amount at signing. That is the unchosen bet, shipping in production. Closing it
is the contribution; [`WHITEPAPER.md §7`](WHITEPAPER.md) maps the prior art and narrows the
claim to exactly what survives.

**The killer demo:** a $10,000/month, 24-month AI contract signed May 2024 costs the buyer
**$240,000 fixed-USD** but only **$44,591 cog-indexed** — the missing **$195,409 (81%)**
is the hidden short, computed from documented prices. Production deals use the **hybrid
template** (fixed USD for the vendor's people-leg + cogs for the cognition leg — index only
what deflates): same deal at $3,000 fixed + 1,000 cogs still saves the buyer **$136,786
(57%)** while the vendor's payroll never deflates.

## Read

- [`WHITEPAPER.md`](WHITEPAPER.md) — the argument: watts-vs-lumens, the fix methodology
  (execution receipts, not posted prices — the LIBOR lesson), basket versioning (the metre/CPI
  machinery), the contracting layer, failure modes including endpoint substitution, and an
  honest prior-art map that concedes what others built first.
- [`spec/`](spec/) — the normative parts, split out so a contract can hash them:
  [`COG-1.md`](spec/COG-1.md) (the unit), [`COG-SETTLE-1.md`](spec/COG-SETTLE-1.md) (settlement,
  the unavailability ladder, chain-linking), [`COG-DENOM-EXT-0.1.md`](spec/COG-DENOM-EXT-0.1.md)
  (denominating an x402 payment or an AP2 mandate in cogs), plus JSON Schemas and their hashes.
  The whitepaper argues; the spec binds.
- [`fixer/PROVENANCE.md`](fixer/PROVENANCE.md) — what the published number does and does not
  measure, including the impurities.

## Run

```sh
# the fix backtest + worked example
python3 cogfix/cogfix.py

# reprice your own contract:  <usd/month> <months> <signed YYYY-MM>
python3 cogfix/cogfix.py --contract 25000 36 2023-06

# hybrid production template: fixed people-leg + indexed cognition leg
python3 cogfix/cogfix.py --contract 10000 24 2024-05 --fixed 3000

# provisional live fix from OpenRouter's public price feed
python3 cogfix/cogfix.py --live

# the dashboard (bending-ruler chart, repricer, live fix)
python3 -m http.server 8483
# → http://localhost:8483/demo/
```

Zero dependencies (Python stdlib + one self-contained HTML file).

## The Fixer — Phase 1, the published price of intelligence

```sh
# free quote mode: publishes fixer/fix.json + dated archive, ssh-signed
python3 fixer/fixerd.py

# receipt-lite mode: REAL micro-buys with execution receipts
# (needs OPENROUTER_API_KEY; spends real money, capped, default $0.50)
python3 fixer/fixerd.py --receipt --max-spend-usd 0.50

# verify any published fix against the signer:
ssh-keygen -Y verify -f fixer/allowed_signers -I cogfix -n cogfix \
  -s fixer/fix.json.sig < fixer/fix.json

# same, for a dated archive entry (archives are signed too):
ssh-keygen -Y verify -f fixer/allowed_signers -I cogfix -n cogfix \
  -s fixer/archive/2026-06-10.json.sig < fixer/archive/2026-06-10.json

# make it daily (cron, 09:07 UTC):
#   7 9 * * * cd <this repo> && python3 fixer/fixerd.py >> fixer/fixerd.log 2>&1
```

First fix published 2026-06-09 (UTC): **1 cog = $0.144** (quote mode — median of the 3
cheapest qualifying posted prices; floor $0.118). Receipt mode implements the same plumbing
with real buys; the full COG-1 depth gate (K=5 × 10M tokens) is the same code with bigger
numbers.

**Trust-anchor caveat.** `fixer/allowed_signers` is written once, at key bootstrap, and is
never rewritten by a later run — but it still ships in the same checkout as the signature it
validates. Verifying both against each other only proves *internal consistency*: a fork with
its own key produces its own equally "valid" `cogfix` signature. For an adversarial check,
obtain the publisher's key fingerprint out of band (signed release tag, published
fingerprint, keyserver) and verify `allowed_signers` against *that* before trusting a fix.
A signature answers "were these bytes altered?", not "is this publisher who they claim?"

## The Qualifying Exam — proving capability instead of assuming it

```sh
python3 harness/qualify.py --self-test    # free: exam integrity + frozen fingerprint
python3 harness/qualify.py --dry-run      # free: full pipeline against mock candidates

# the real keuring: sit every allowlisted model for the exam (spends money, capped)
OPENROUTER_API_KEY=... python3 harness/qualify.py --max-spend-usd 0.25
```

The exam (`harness/exam_core.json`, **COG1-CORE-v0**, 40 auto-gradable items, threshold
80%) has a frozen sha256 fingerprint published with every result. A real run writes
`fixer/qualified.json`; while fresh (≤ 7 days) **fixerd gates the fix on it** and the
published fix says `"basis": "exam-qualified"` — otherwise it falls back to the static
allowlist and says so. Every published fix declares what its qualification rests on.
v0 honesty: the core is a basic capability floor (catches junk/broken/mislabeled models);
tier calibration against known models is pending, and the private rotating audit set
(contamination detection, WHITEPAPER §5) is deliberately not in this repo.

Tests: `python3 -m unittest discover -s tests` — **69 tests, no network, stdlib only**: fix math,
hybrid repricing, grading, exam integrity and fingerprint scope, spend caps, MCP protocol and
tool surface, the qualification gate, signature replacement and tamper detection, all five
settlement rungs, Decimal invoice arithmetic, archive recomputation, rail fixtures, and the
step-function anchor. One of them executes the reference invoice's own `recompute` string
verbatim and requires exit 0 — a self-verifying invoice whose verification command doesn't run
is worse than none.

## Denominate a contract — the part nobody else ships

A published number is not an obligation. This is the machinery that turns one into the other.

```sh
# settle a cog-denominated obligation for a billing period
python3 contracts/settle.py --settle contracts/examples/reference-cdo.json --period 2026-09

# ...and check the vendor's arithmetic yourself, with no key material
python3 contracts/settle.py --verify contracts/examples/reference-invoice.json \
  --archive fixer/archive
```

The invoice carries the sha256 and signature verdict of **every archived fix it used**, the
settlement status label, and its own recompute command. Flip one byte in one archived fix and
verification fails. A payer can audit a bill without trusting the payee, the publisher, or us.

What the spec pins down that a price series alone cannot:

- **Settlement Fix** — median over a window anchored to the period end, not the invoice date,
  so neither party can shop for a favourable window.
- **The unavailability ladder** — publication *will* fail. `normal` → `degraded-window` →
  `carry-forward` → `anchor-fallback` (provisional, unpayable until acknowledged, subject to
  true-up) → `converted` (at 90 days, remaining cogs convert to USD). Every rung is labeled on
  the invoice. A settlement system whose failure modes are invisible is worse than one with none.
- **Chain-linking** — when COG-1 is retired for COG-2, obligations convert at a linking factor
  measured over a parallel-publication window. The metre survived four redefinitions without
  breaking contracts written in metres.
- **Rider templates** ([`contracts/riders/`](contracts/riders/)) — enterprise MSA, MSA with a
  collar, agent-to-agent SLA, metered true-up, and an **RFP clause**: the five sentences a
  buyer drops into a tender. That last one is the cheapest adoption lever here.
- **Denomination extension** — an x402 payment or an AP2 recurring mandate carries a cog
  quantity while the rails keep settling in stablecoin. No wallet, chain, or facilitator
  changes. A mandate that freezes a dollar amount at signing is the bet nobody chose.

Money arithmetic is `decimal.Decimal`, half-up, fix at 6dp and amounts at 2dp — stated in the
spec, because float rounding is the classic source of indexed-contract disputes.

## MCP server — the fix in every agent's hands

```sh
claude mcp add cog-fix -- python3 "$PWD/mcp/cog_mcp.py"
```

Nine tools, zero dependencies. Pricing: `get_fix` (today's price of intelligence),
`price_in_cogs` (convert USD or token workloads), `reprice_contract` (hidden-short analysis,
hybrid leg supported). Contracting: `generate_sla` and `generate_rider` (the template library),
`draft_obligation` (a validated CDO), `settlement_fix`, `settle_invoice`, `verify_invoice`.

**Five resolution rungs, each labeled with the evidence it earned** — `receipted-depth` →
`venue-quote` → `venue-quote-live` → `external-anchor` (Epoch AI, CC BY) →
`bundled-snapshot`. The bottom two are marked `NON-SETTLEABLE` and `settle.py` refuses them: a
fallback that quietly settles an invoice off a stale research CSV is precisely the failure the
whitepaper's LIBOR argument condemns. `get_fix` reports the rung, the age, the receipt count,
and the qualification basis, so an agent can tell a receipted price from a posted guess.

## Status & honesty

Draft 0.3, July 2026. The backtest uses **documented launch/posted prices as a proxy** for
receipted runs and is approximate by construction — every point is sourced and labeled in
[`cogfix/data.json`](cogfix/data.json), with venue, promotional status, and dating caveats
recorded per point. See [`fixer/PROVENANCE.md`](fixer/PROVENANCE.md) for what the published
number does and does not measure.

**The novelty claim was too broad and has been narrowed.** Draft 0.2 claimed a three-way fusion
— capability-normalized pricing × receipt-verified fix × contracting layer — and asserted no
prior work had two legs. Two of those legs turned out to be built: Epoch AI publishes the
capability-normalized series (open, CC BY), Ornn publishes a receipt-verified token index, and
arXiv 2603.21690 proposed a frozen-capability token unit before we did. arXiv 2511.23455 had
already measured the "algorithmic-efficiency premium" we called unpriceable. All of it is now
in [`WHITEPAPER.md §7`](WHITEPAPER.md), and the claim is down to two things: **contract
denomination mechanics**, and **the depth protocol** that makes a receipt mean something.

**What has not been exercised:** the depth requirement is the load-bearing claim and no buy at
spec size (K=5 × 10M tokens) has ever run. Receipts published so far are `[]`. Until that
changes this is a specification with a reference implementation, not an operating index — and
the repo says so rather than implying otherwise.

## Licensing

Permissive, with attribution. Two licenses, because this repository is half software and half
argument:

| What | License | File |
|---|---|---|
| Code — `cogfix/`, `fixer/`, `harness/`, `mcp/`, `anchor/`, `contracts/`, `tests/`, `demo/` | Apache License 2.0 | [`LICENSE`](LICENSE) |
| Prose and spec — `WHITEPAPER.md`, `README.md`, `spec/`, riders | CC BY 4.0 | [`LICENSE-DOCS`](LICENSE-DOCS) |

**In plain terms:** use it, fork it, sell it, close-source your changes, run your own competing
fixer. You owe nothing and need no permission. You must keep the ProofOfWork Agency attribution
— see [`NOTICE`](NOTICE), which Apache §4(d) requires you to carry into derivative works.

This is deliberate rather than default. A unit of account that others cannot freely adopt,
fork, and independently publish is not a unit of account — it is a product. The whitepaper
argues that any party should be able to become a fixer and any party should be able to audit
one; the license has to actually permit that. Attribution is the only thing withheld.

Price data derived from Epoch AI is used under CC BY 4.0 and attributed in
[`NOTICE`](NOTICE), in `anchor/snapshot/SOURCE.md`, and in every fix payload that cites the
anchor. Their attribution is not substituted by ours.
