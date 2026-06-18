# Self Training Loop

UltraBrain should self-train only from verified experience.

The loop:

```text
task
-> attempt
-> verification
-> evidence
-> correction if needed
-> trusted training trace
-> batch fine-tune
-> evaluation
-> promote only if better
```

## Two Kinds Of Learning

Memory learning is immediate:

```text
this command failed
this test passed
this user correction is trusted
this file changed
```

Weight learning is delayed:

```text
collect verified traces
train a local student model
run evaluations
promote only if it improves
```

This avoids poisoning the model with unverified teacher answers.

## Training Trace Shape

A useful trace contains:

```json
{
  "task": "Solve 2*x + 3 = 11",
  "attempt": "x = 5",
  "verification": "failed: 2*5 + 3 = 13",
  "correction": "x = 4",
  "proof": "2*4 + 3 = 11",
  "trusted": true
}
```

For code:

```json
{
  "task": "Fix failing test",
  "attempt": "patch A",
  "verification": "pytest failed",
  "correction": "patch B",
  "proof": "pytest passed",
  "trusted": true
}
```

Mistakes are valuable, but only after the system records the correction and the
evidence that proves the correction.

## Version Meaning

- v0.1: learns into memory
- v0.2: creates verified datasets
- v0.3: trains local neural students
- v0.4: promotes or rejects trained models by evaluation
- v1.0: integrated self-learning brain

