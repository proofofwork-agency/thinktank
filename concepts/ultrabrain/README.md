# UltraBrain

> **Status: concept** — working prototype, verdicted. See [docs/SPARRING.md](docs/SPARRING.md)
> for why it exists, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how, and
> [docs/DEMO.md](docs/DEMO.md) for real receipts. Whitepaper: [WHITEPAPER.md](WHITEPAPER.md).

A from-scratch LLM that is **not** the memory and **not** the logic — only the perception.

Born from a sparring session about what's wrong with LLMs: prediction is unbeaten as a
*learning rule for raw text*, but statelessness is just a multi-tenancy artifact, and
sampled tokens are not reasoning. UltraBrain splits the brain:

| Layer | Mechanism | Properties |
|---|---|---|
| Perception | tiny GPT, trained from scratch here | stochastic, replaceable |
| Acquisition | **Generate → Verify → Keep** gate | only verified facts/rules are written |
| Memory | append-only JSONL ledger per user | persists across restarts, no context resend |
| Reasoning | semi-naive Datalog with proof traces | deterministic, explainable |

The LM proposes, the verifier disposes, the ledger remembers, Datalog derives.
LM randomness can never corrupt knowledge. Answers are labeled `proved` (with `why`
derivation) or refused — never guessed into the KB.

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
