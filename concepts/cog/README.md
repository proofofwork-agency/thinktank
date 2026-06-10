# THE C⚙G

**A capability-indexed unit of account for the intelligence economy.**
Not a coin. Not a chain. A ruler that doesn't bend.

---

The price of cognition falls ~10× per year (GPT-4-class inference: **$36.00 → $0.25 per
million blended tokens in 39 months**). Every AI contract denominated in dollars is therefore
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
cog is the same machine pointed at *deflation of intelligence*: as far as we can tell, the
first deflation-native unit of account.

**The killer demo:** a $10,000/month, 24-month AI contract signed May 2024 costs the buyer
**$240,000 fixed-USD** but only **$44,591 cog-indexed** — the missing **$195,409 (81%)**
is the hidden short, computed from documented prices. Production deals use the **hybrid
template** (fixed USD for the vendor's people-leg + cogs for the cognition leg — index only
what deflates): same deal at $3,000 fixed + 1,000 cogs still saves the buyer **$136,786
(57%)** while the vendor's payroll never deflates.

## Read

- [`WHITEPAPER.md`](WHITEPAPER.md) — the full invention: watts-vs-lumens, the fix
  methodology (execution receipts, not posted prices — the LIBOR lesson), basket versioning
  (the metre/CPI machinery), the contracting layer, failure modes, honest prior-art map.

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

# make it daily (cron, 09:07 UTC):
#   7 9 * * * cd <this repo> && python3 fixer/fixerd.py >> fixer/fixerd.log 2>&1
```

First fix published 2026-06-09 (UTC): **1 cog = $0.144** (quote mode — median of the 3
cheapest qualifying posted prices; floor $0.118). Receipt mode implements the same plumbing
with real buys; the full COG-1 depth gate (K=5 × 10M tokens) is the same code with bigger
numbers.

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

Tests: `python3 -m unittest discover -s tests` (22 tests: fix math, hybrid repricing,
grading, exam integrity, MCP protocol, qualification gate).

## MCP server — the fix in every agent's hands

```sh
claude mcp add cog-fix -- python3 "$PWD/mcp/cog_mcp.py"
```

Four tools, zero dependencies: `get_fix` (today's price of intelligence),
`price_in_cogs` (convert USD or token workloads), `reprice_contract` (hidden-short
analysis, hybrid leg supported), `generate_sla` (cog-denominated pricing rider text).
Resolution order: published `fixer/fix.json` → live OpenRouter quote → bundled snapshot.

## Status & honesty

Draft 0.2, June 2026. The backtest uses **documented launch/posted prices as a proxy** for
receipted runs and is approximate by construction — every point is sourced and labeled in
[`cogfix/data.json`](cogfix/data.json). Prior art is mapped, not hidden: a16z's LLMflation
observed the curve, Artificial Analysis tracks the tiers, compute.finance indexes token
prices (watts, not lumens), Chile's UF proved the unit-of-account template. The claimed
novelty is precisely the fusion: *capability-normalized outcome pricing × receipt-verified
daily fix × unit-of-account contracting layer.*
