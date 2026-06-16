# Math-First Curriculum

Math and algebra are the first serious learning domain because they have a
truth oracle. That makes them ideal for self-learning:

```text
problem -> local/teacher proposal -> deterministic verifier -> accepted/rejected trace
```

The system does not need to trust a language model to know whether `x=4` solves
`2*x + 3 = 11`. It can check it exactly.

## Implemented v0

`ultrabrain/math_core.py` provides:

- exact rational arithmetic
- operator precedence
- parentheses
- implicit multiplication such as `2x`
- one-variable linear equation solving
- proof steps
- rejection of unsupported nonlinear algebra

Agent commands:

```bash
python3 agent.py --cmd 'math 2 + 3 * 4 => 14'
python3 agent.py --cmd 'math 2*x + 3 = 11 => x=4'
python3 agent.py --cmd 'teacher-math 2*x + 3 = 11 => x=5'
```

Every math command writes:

```text
episode
action
verifier result
accepted/rejected training candidate
failure record when wrong
```

## Why This Comes Before Files

Files and projects are messy. Math gives us a clean loop:

```text
generate question
ask local model or teacher
check answer exactly
store result
train from verified examples
run evals
```

Once this works, the same learning machinery can be reused for code, documents,
and tools where verification is harder.

## Curriculum Ladder

1. Arithmetic
   - addition, subtraction, multiplication, division
   - parentheses and precedence
   - fractions

2. Linear algebra basics
   - simplify `ax + b`
   - solve `ax + b = c`
   - solve equations with variables on both sides

3. Algebra skills
   - distribute
   - factor simple forms
   - isolate variables step by step
   - detect no-solution and identity equations

4. Word problems
   - translate language into equations
   - verify equation against source text
   - solve
   - explain result

5. Multi-step proofs
   - require every step to preserve equality
   - reject invalid transformations
   - store reusable solving procedures as skills

6. Training
   - train a local translator from word problems to equations
   - train a step selector for algebra transformations
   - train a skill retriever for problem families

## Teacher Usage

Teacher LLMs should be asked narrow questions:

```text
Translate this word problem into one equation.
Suggest the next valid algebra step.
Generate 20 linear equation examples.
Explain why this wrong answer failed.
```

Teacher output is accepted only when the math verifier can check it.

## Next Build

The next math-specific build should add:

- generated arithmetic/algebra drills
- equation-step verifier
- word-problem schema
- teacher question generator
- eval set for local-vs-teacher performance
- adapter training export from `training_queue.jsonl`
