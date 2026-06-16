# UltraBrain Thought Log

This folder captures the current design thinking around UltraBrain as a durable set
of notes. These files are not a final specification. They preserve the reasoning
path so later roadmap work can separate strong bets from weak assumptions.

## North Star

UltraBrain exists to reduce dependence on single-company LLM hegemony. The aim is
not to replace one chatbot with another. The aim is to own the learning loop:
memory, evidence, corrections, skills, verified traces, evaluations, and modular
models.

Intelligence should not be locked inside one company's dense weights. External
LLMs can be useful teachers, but they should not be permanent rulers of the
system's memory or improvement loop.

## Notes

- [00 - Beat Single-Company LLM Hegemony](00_NORTH_STAR_single_company_llm_hegemony.md)
- [21 - Brain, Not One Giant Model](21_brain_not_one_giant_model.md)
- [22 - Trust Boundary And Verification](22_trust_boundary_and_verification.md)
- [23 - Beyond Token Prediction](23_beyond_token_prediction.md)
- [24 - Self Training Loop](24_self_training_loop.md)
- [25 - Scaling With Less Brute Force](25_scaling_with_less_brute_force.md)
- [26 - Research Threads](26_research_threads_summary.md)

## Working Thesis

UltraBrain should not begin as an attempt to clone a frontier GPT. The stronger
idea is to build a brain-like system where intelligence comes from the loop
between memory, action, verification, skill formation, and selective neural
training.

The core direction:

```text
observe
-> propose action
-> verify against tools or evidence
-> store trusted memory
-> extract reusable skill
-> train smaller neural parts
-> evaluate before promotion
```

The strategic goal is independence from one giant model provider. That does not
mean refusing existing LLMs. It means using them as temporary teachers while the
system accumulates its own verified traces, memory, skills, and specialist
models.
