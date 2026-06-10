"""Deterministic gate: only verified statements enter the KB."""

import re

from .datalog import Rule, parse_atom

try:
    from data.synth import POOLS
    ENTITIES = {e for pool in POOLS.values() for e in pool}
except ImportError:
    ENTITIES = set()


def known_entities(sentence):
    words = re.findall(r"[a-z]+|\d+", sentence.lower())
    return [w for w in words if w in ENTITIES or w.isdigit()]

SCHEMAS = {"capital": 2, "lives_in": 2, "parent": 2, "works_at": 2, "located_in": 2,
           "grandparent": 2, "compatriot": 2, "colleague": 2, "age": 2, "older": 2}
# functional: first argument determines a unique second argument
FUNCTIONAL = {"capital", "located_in", "lives_in", "works_at", "age"}
BUILTINS = {"neq", "lt", "gt"}


# keyword -> predicate, and the pool that fills slot 0 vs 1 (None = ambiguous, no repair)
PRED_HINTS = [
    ("years old|age|how old", "age", ("PEOPLE", "NUM")),
    ("older", "older", None),
    ("grandparent|grandmother|grandfather", "grandparent", None),
    ("compatriot|same city", "compatriot", None),
    ("colleague", "colleague", None),
    ("capital", "capital", ("COUNTRIES", "CITIES")),
    ("live|resides", "lives_in", ("PEOPLE", "CITIES")),
    ("parent|mother|father|child", "parent", None),
    ("work|employ|job", "works_at", ("PEOPLE", "COMPANIES")),
    ("located|city in|find", "located_in", ("COUNTRIES", "CITIES")),
]


STOP = {"is", "are", "the", "a", "of", "in", "at", "and", "old", "year", "years", "who",
        "what", "where", "which", "how", "does", "do", "live", "lives", "work", "works",
        "than", "older", "age", "capital", "located", "parent", "mother", "father", "by"}


def _pick(pool, ents, words=()):
    if pool == "NUM":
        return next((e for e in ents if e.isdigit()), "X")
    hit = next((e for e in ents if e in POOLS.get(pool, ())), None)
    if hit is None and pool == "PEOPLE":  # open world: any name-like word
        hit = next((w for w in words if w not in STOP and not w.isdigit() and w not in ents), None)
    return hit or "X"


def _slot(args_pools, ents, words=()):
    if not args_pools:
        return None
    return _pick(args_pools[0], ents, words), _pick(args_pools[1], ents, words)


def repair_query(question, proposal):
    """Deterministically rebuild query candidates from the question's own words."""
    q = question.lower()
    for pat, pred, pools in PRED_HINTS:
        if re.search(pat, q):
            ents = known_entities(q)
            if pools:
                a, b = _slot(pools, ents)
                return [f"{pred}({a},{b})"]
            if ents:  # ambiguous slot order: ask both directions
                return [f"{pred}({ents[0]},X)", f"{pred}(X,{ents[0]})"]
            return [f"{pred}(X,X)"]
    return [proposal]


def repair_fact(sentence):
    """Deterministic fallback when the LM can't translate faithfully: unambiguous predicates only."""
    s = sentence.lower()
    words = re.findall(r"[a-z]+|\d+", s)
    for pat, pred, pools in PRED_HINTS:
        if pools and re.search(pat, s):
            a, b = _slot(pools, known_entities(s), words)
            if "X" not in (a, b):
                return f"{pred}({a},{b})"
    return None


def verify_fact(stmt, facts, source=None):
    try:
        pred, args = parse_atom(stmt)
    except ValueError:
        return None, "rejected: not of the form pred(a,b)"
    if source is not None:
        s = source.lower()
        missing = [a for a in args if a.replace("_", " ") not in s]
        if missing:
            return None, f"rejected: unfaithful — {','.join(missing)} not in the sentence"
        dropped = [e for e in known_entities(s) if e not in args]
        if dropped:
            return None, f"rejected: unfaithful — sentence mentions {','.join(dropped)} but proposal drops it"
    if pred not in SCHEMAS:
        return None, f"rejected: unknown predicate '{pred}'"
    if len(args) != SCHEMAS[pred] or not all(args):
        return None, f"rejected: {pred} needs {SCHEMAS[pred]} arguments"
    if pred == "parent" and args[0] == args[1]:
        return None, "rejected: nobody is their own parent"
    fact = (pred, args)
    if fact in facts:
        return None, "duplicate: already known"
    if pred in FUNCTIONAL:
        for f in facts:
            if f[0] == pred and f[1][0] == args[0] and f[1][1] != args[1]:
                return None, f"contradiction: {pred}({args[0]},{f[1][1]}) already verified"
    return fact, "verified"


def verify_rule(stmt, rules):
    try:
        r = Rule.parse(stmt)
    except Exception:
        return None, "rejected: not a valid rule (head :- body)"
    for pred, args in [r.head, *r.body]:
        if pred in BUILTINS and (pred, args) in r.body and len(args) == 2:
            continue
        if pred not in SCHEMAS:
            return None, f"rejected: unknown predicate '{pred}'"
        if len(args) != SCHEMAS[pred]:
            return None, f"rejected: {pred} arity"
    if any(r.text == x.text for x in rules):
        return None, "duplicate: rule already known"
    head_vars = {t for t in r.head[1] if t[:1].isupper()}
    body_vars = {t for a in r.body for t in a[1] if t[:1].isupper()}
    if not head_vars <= body_vars:
        return None, "rejected: unbound variable in head"
    return r, "verified"
