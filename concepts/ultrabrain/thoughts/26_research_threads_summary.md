# Research Threads

These are research directions worth tracking for UltraBrain. They are not all
equally mature, but each attacks a different piece of the current LLM stack.

## Tokenizer-Free Or Token-Lighter Models

Goal: reduce dependence on fixed subword tokenizers.

- Byte Latent Transformer: raw bytes with dynamic patches
- ByT5: byte-to-byte sequence modeling
- MEGABYTE: multiscale byte modeling for long sequences
- Charformer: learns latent subword representations from characters

Relevance:

```text
good for multilingual text, code, binary-like data, noisy text, and less tokenizer debt
```

## Non-Autoregressive And Diffusion Text Models

Goal: avoid strict one-token-at-a-time generation.

- Diffusion-LM
- non-autoregressive machine translation
- latent diffusion text generation

Relevance:

```text
could improve parallel generation, revision, fill-in-the-middle, and controllability
```

Risk:

```text
text quality and dependency modeling are still hard
```

## Transformer Alternatives

Goal: reduce attention cost and improve long-context scaling.

- Mamba and selective state-space models
- recurrent or linear-time sequence models
- hybrid attention/state-space models

Relevance:

```text
could make long memory/context cheaper
```

Important caveat:

```text
changing the architecture does not automatically change the next-token objective
```

## Neuro-Symbolic Systems

Goal: combine neural proposal with symbolic verification and reusable skills.

- DreamCoder: grows reusable program abstractions and neural search policies
- AlphaGeometry: neural guidance plus deduction engine and synthetic proof data
- Toolformer: learns tool-use behavior from limited demonstrations
- theorem proving systems: proof-step generation plus formal verification

Relevance:

```text
this is the closest family to UltraBrain
```

UltraBrain should study these because they show a path where intelligence grows
from:

```text
search
+ tools
+ proof
+ reusable abstractions
+ verified synthetic data
```

## First Research Question

The first decisive experiment should be:

```text
Can a small model trained on UltraBrain traces choose better verified next actions
than a normal small LLM?
```

If yes, UltraBrain has a credible path beyond ordinary token prediction.

