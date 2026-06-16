# UltraBrain

> **Status: v0.4 — the generator pivot.** The active build is a **verifier-grounded
> generator**: generation by *search + verify*, not next-token prediction. It runs on a
> hardened substrate — capability trust boundary, a working Truth Maintenance System, KB as a
> live projection of the evidence store, the decisive A/B experiment **passing all five bars**,
> a per-test project brain, and an action-prediction core. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
> for how, [docs/DEMO.md](docs/DEMO.md) for receipts, [docs/ROADMAP.md](docs/ROADMAP.md) for the
> arc, [thoughts/00_INDEX.md](thoughts/00_INDEX.md) for the research spine, and
> [WHITEPAPER.md](WHITEPAPER.md) for the thesis.

**The bet: replace next-token prediction as the foundation of generation.** Not "a better
LLM" — a *verifier-grounded generator* that produces answers by **search + verify**, so every
emitted answer is correct *by construction* or it abstains. This is how single-company LLM
hegemony breaks: value moves from "one giant predictor trained on megawatts" to the verifier +
composition + local-learning layer ([thoughts/00_INDEX.md](thoughts/00_INDEX.md)). Honest scope
([thoughts/23_beyond_token_prediction.md](thoughts/23_beyond_token_prediction.md)): replacing
token generation *entirely* is unsolved; replacing it for a *verifiable* domain is realistic now
— and shipping (v0.4, math): `solve-search` returns a verified derivation, never sampled tokens.

Everything below is the **scaffolding that makes such a generator trainable** — the verifier is
its teacher, verified traces are its data. To build a thing that says "is this output correct?"
you first need the verifier, the evidence store, the memory, and the trust boundary. So UltraBrain
splits the brain — the LLM is **not** the memory, **not** the logic, and **not** the judge, only
perception and proposal:

| Layer | Mechanism | Properties |
|---|---|---|
| **Generator (v0.4)** | generation = **search + verify**, not token sampling | every emitted answer is verified-correct by construction or it abstains; the policy only makes search efficient, never correctness |
| Perception | tiny GPT, trained from scratch here | stochastic, replaceable |
| Acquisition | **capability-gated** Generate → Verify → Keep | trusted memory needs an unforgeable in-process grant from a real oracle/user — not a string argument |
| Memory | append-only JSONL + hash chain + **TMS** | persists across restarts; conflicts retract/supersede; tamper-evident ledger |
| Reasoning | Datalog proof fixture + evidence proofs | deterministic where an oracle exists; KB is a live projection of the evidence store (single writer) |
| Experience | append-only step ledgers | every action becomes learning material |
| Evidence | oracle/user-backed records | trusted beliefs trace to exact evidence; `why-belief` shows the command + digest |
| Skills | Markdown procedural memory | verified procedures are retrieved before acting |
| Action core (v0.3) | predict the next **verified action**, not the next token | trained on actions a verifier blessed; eval is verified-yield vs baselines |
| Project brain (M2/M6) | read-only tool oracles → project predicates + `fix_verified_by` | remembers a codebase across restarts; connects fixes to verifying tests; auto-retracts on regression |

The LM proposes; oracles, user corrections, and deterministic trust policy decide what
can become trusted. In v0.3 the trust boundary is a **capability**, not a naming
convention: oracle-rank memory requires a grant that only a real tool run (pytest, git
diff, import check, math verify) or an explicit user assertion can mint. A real **TMS**
retracts and supersedes conflicting beliefs (functional *and* cross-predicate), the KB is
a live typed projection of the evidence store so the two can never silently disagree, and
an append-only **hash chain** makes the ledger tamper-evident (git's model — tamper-
evident, not authenticated; HMAC/signed checkpoints are the noted upgrade path).

The new agent layer extends the thesis:

```
task -> context assembler -> local/teacher model proposes -> verifier gates
     -> trusted memory / refusal -> experience ledger -> skill/training candidate

tool -> evidence record -> active belief -> why-belief links back to command + digest
```

Teacher LLMs may bootstrap the system, but they never write trusted memory directly.
Their outputs become proposals or training candidates until an oracle/user path promotes them.

Everything from scratch: byte-BPE tokenizer, manual causal attention (no `nn.Transformer`,
no SDPA), RMSNorm, SwiGLU, trains in minutes on Apple MPS. Arithmetic builtins (`lt`, `gt`,
`neq`) make rules like `older(A,B) :- age(A,X), age(B,Y), gt(X,Y)` provable. One frozen
model, many users: each `--user` gets an isolated ledger. See `WHITEPAPER.md` for the thesis.

## Run

```bash
curl -sL https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt -o data/shakespeare.txt
python3 train.py                 # tokenizer + GPT on Shakespeare + NL→logic pairs
python3 -m pytest tests -q      # core tests
python3 brain.py --user you     # REPL: tell / ask / why / learn / forget / kb / gen
```

Agent runtime, no checkpoint required:

```bash
python3 agent.py --user you \
  --cmd 'tell parent(maria,jan)' \
  --cmd 'tell parent(jan,sofia)' \
  --cmd 'learn grandparent(X,Z) :- parent(X,Y), parent(Y,Z)' \
  --cmd 'ask grandparent(maria,Z)'
```

Math/algebra curriculum:

```bash
python3 agent.py --user you \
  --cmd 'math 2 + 3 * 4 => 14' \
  --cmd 'math 2*x + 3 = 11 => x=4' \
  --cmd 'teacher-math 2*x + 3 = 11 => x=5'
```

Teacher-gated bootstrap:

```bash
python3 agent.py --user you \
  --cmd 'teacher the capital of netherlands is rotterdam => capital(netherlands,rotterdam)'
```

If the proposal contradicts the verified ledger, it is rejected and saved as a rejected
training candidate instead of becoming memory. If it merely passes the toy syntax gate,
it is still untrusted until an oracle/user path promotes it.

Oracle-backed evidence:

```bash
python3 agent.py --user you \
  --cmd 'oracle-git-diff .' \
  --cmd 'oracle-pytest . -- -q' \
  --cmd 'why-belief pytest_passed(0)'
```

Truth maintenance + tamper-evident audit (v0.3):

```bash
python3 agent.py --user you \
  --cmd 'tell parent(maria,jan)' \
  --cmd 'retract parent(maria,jan) => correction' \
  --cmd 'why-belief parent(maria,jan)' \
  --cmd 'verify-ledger'
```

Decisive A/B experiment — UltraBrain vs a frontier-style agent + vector DB, offline and
deterministic. System B clears all five bars (higher task success, lower repeated
failures, far smaller context, 100% provenance, zero unsupported trusted writes):

```bash
python3 -m experiment.run_experiment --sessions 5 --out experiment/results
```

v0.3 action-prediction core — predict the next **verified action**, not the next token:

```bash
python3 train_actions.py            # train on verified-action traces (synthetic + real)
python3 eval_actions.py             # verified-yield vs majority / random baselines
```

Local project brain (M2 tool layer + M6 domain) — point it at a real repo, build verified
memory, connect fixes to the tests that verified them:

```bash
python3 agent.py --user you \
  --cmd 'ingest .' \
  --cmd 'oracle-compile ultrabrain/evidence.py' \
  --cmd 'oracle-search EvidenceStore' \
  --cmd 'why-belief fix_verified_by(ultrabrain/kb.py,0)'
```

`ingest` runs a read-only tool battery (git diff, import checks, `py_compile`, pytest) and
records `compiles_ok` / `imports_ok` / `file_contains` / `changed_file` / `pytest_passed`,
then derives `fix_verified_by(change, pytest_exit)` for every changed file consistent with a
passing suite — which the TMS **auto-retracts the moment a later test fails** (connecting
fixes to tests, and avoiding known-bad fixes). Dogfooding: UltraBrain ingests its **own**
repo (35 `compiles_ok`, 8 `imports_ok`, 7 `fix_verified_by`, each with a proof chain back to
the exact tool command) — the project brain that knows its own codebase.

Demo of the point:

```
> tell maria is the mother of jan        # LM → parent(maria,jan) → verified → kept
> tell jan lives in utrecht
> learn grandparent(X,Z) :- parent(X,Y), parent(Y,Z)
^D  (restart — zero context carried)
> ask grandparent(maria,Z)
> why grandparent(maria,sofia)           # derivation tree, provenance
> tell capital(netherlands,rotterdam)    # contradiction → rejected
```
