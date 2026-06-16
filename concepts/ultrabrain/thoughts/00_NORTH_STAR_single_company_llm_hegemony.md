# Beat Single-Company LLM Hegemony

## Problem

A few companies control the strongest frontier models, the training loops that
improve them, the user memory that makes them personalized, the feedback data
that compounds advantage, and the deployment access that decides who can build
on top of them.

That creates a technical dependency:

```text
intelligence lives inside someone else's dense weights
```

It also creates a strategic dependency:

```text
the more we use the system, the stronger their private learning loop becomes
```

## UltraBrain Answer

UltraBrain should move durable intelligence out of a single provider's hidden
model weights and into user-owned, portable systems:

- memory
- evidence
- tools
- skills
- corrections
- verified traces
- modular models
- evaluation results

The goal is not to reject frontier LLMs. The goal is to prevent them from being
the only place where learning accumulates.

## Strategic Goal

Use frontier LLMs when they are useful, but make every interaction increase our
own independent system.

```text
external LLM proposes
-> UltraBrain verifies
-> evidence is stored locally
-> trusted memory improves
-> reusable skills are extracted
-> verified traces train modular models
-> dependency on the external model decreases
```

## Design Consequence

The main asset is not one model file. The main asset is the learning loop:

```text
task
-> proposal
-> tool action
-> verification
-> memory
-> skill
-> training trace
-> evaluation
-> better local or modular capability
```

This makes LLM hegemony an architecture constraint. UltraBrain should be built so
knowledge, corrections, evidence, and skills remain inspectable and transferable
instead of being absorbed only into a private model.

## Open Question

What is the smallest prototype that proves this thesis clearly: a system that
uses a frontier model as teacher but measurably grows its own independent memory,
skills, and action policy over repeated tasks?

