# Receipts — real session transcripts (2026-06-10, 10M model, MacBook MPS)

Training: 99%+ held-out accuracy, ~9 min. KB ingested once; restarts carry zero context.

## Hallucination cannot land (Generate → Verify → Keep, live)

```
> maria works at asml
  LM proposes: works_at(maria,liam)  ->  rejected: unfaithful — liam not in the sentence
  LM proposes: works_at(maria,ruben) ->  rejected: unfaithful — ruben not in the sentence
  gate rebuilds: works_at(maria,asml)  ->  verified
```

## Restart, ask in plain language, get proofs

```
ultrabrain · user=danillo · facts/rules loaded from ledger (zero context resend)
> where does maria work
  proved: maria works at asml   [works_at(maria,asml)]
> who is the grandparent of jan
  proved: lucas is a grandparent of jan   [grandparent(lucas,jan)]
> why grandparent(lucas,jan)
  grandparent(lucas,jan)   [via grandparent(X,Z) :- parent(X,Y), parent(Y,Z)]
    parent(lucas,maria)   [told]
    parent(maria,jan)   [told]
```

## Contradiction refused; no guessing

```
> tell rotterdam is the capital of the netherlands
  LM proposes: capital(netherlands,rotterdam)  ->  contradiction: capital(netherlands,amsterdam) already verified
> where does jan work
  no proof (won't guess into the KB)
```

## Arithmetic with proofs; users isolated

```
[user remco]            [user danillo]
> remco is 52 years old        > ask capital(france,X)
  gate rebuilds: age(remco,52)   no proof   ← remco's France never leaked
> why older(remco,maria)
  older(remco,maria) [via older(A,B) :- age(A,X), age(B,Y), gt(X,Y)]
    age(remco,52) [told] · age(maria,34) [told] · gt(52,34) [builtin]
```
