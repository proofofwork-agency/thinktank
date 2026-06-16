"""Deterministic gate: only verified statements enter the KB."""

import re

from .datalog import Rule, is_var, parse_atom

try:
    from data.synth import POOLS
    ENTITIES = {e for pool in POOLS.values() for e in pool}
except ImportError:
    POOLS = {}
    ENTITIES = set()


def tokens(text):
    return re.findall(r"[a-z]+|\d+", text.lower().replace("_", " "))


def known_entities(sentence):
    words = tokens(sentence)
    return [w for w in words if w in ENTITIES or w.isdigit()]

SCHEMAS = {
    "capital": ("COUNTRY", "CITY"),
    "lives_in": ("PERSON", "CITY"),
    "parent": ("PERSON", "PERSON"),
    "works_at": ("PERSON", "COMPANY"),
    "located_in": ("COUNTRY", "CITY"),
    "grandparent": ("PERSON", "PERSON"),
    "compatriot": ("PERSON", "PERSON"),
    "colleague": ("PERSON", "PERSON"),
    "age": ("PERSON", "NUM"),
    "older": ("PERSON", "PERSON"),
}
# functional: first argument determines a unique second argument
FUNCTIONAL = {"capital", "located_in", "lives_in", "works_at", "age"}
BUILTINS = {"neq", "lt", "gt"}

# Predicate pairs that cannot both hold for the same first-argument subject.
# Used by the TMS to supersede a contradictory active belief on a *different*
# predicate (the functional/key mechanism only catches same-key conflicts).
CONTRADICTS = {
    "imports_ok": "imports_broken",
    "imports_broken": "imports_ok",
}


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
    words = tokens(s)
    for pat, pred, pools in PRED_HINTS:
        if pools and re.search(pat, s):
            a, b = _slot(pools, known_entities(s), words)
            if "X" not in (a, b):
                return f"{pred}({a},{b})"
    return None


def _arity(pred):
    return len(SCHEMAS[pred])


def _domain_ok(domain, arg, source_tokens=None):
    if domain == "NUM":
        return arg.isdigit()
    pools = {
        "PERSON": "PEOPLE",
        "CITY": "CITIES",
        "COUNTRY": "COUNTRIES",
        "COMPANY": "COMPANIES",
    }
    pool = set(POOLS.get(pools[domain], ()))
    if arg in pool:
        return True
    if domain == "PERSON" and source_tokens is not None:
        arg_tokens = tokens(arg)
        other_entities = set().union(
            set(POOLS.get("CITIES", ())),
            set(POOLS.get("COUNTRIES", ())),
            set(POOLS.get("COMPANIES", ())),
        )
        return bool(arg_tokens) and set(arg_tokens) <= source_tokens and arg not in other_entities
    return False


def verify_fact(stmt, facts, source=None):
    try:
        pred, args = parse_atom(stmt)
    except ValueError:
        return None, "rejected: not of the form pred(a,b)"
    if pred not in SCHEMAS:
        return None, f"rejected: unknown predicate '{pred}'"
    if len(args) != _arity(pred) or not all(args):
        return None, f"rejected: {pred} needs {_arity(pred)} arguments"
    if any(is_var(a) for a in args):
        return None, "rejected: ground facts cannot contain variables"
    source_tokens = None
    if source is not None:
        source_tokens = set(tokens(source))
        missing = [a for a in args if not set(tokens(a)) <= source_tokens]
        if missing:
            return None, f"rejected: unfaithful — {','.join(missing)} not in the sentence"
        dropped = [e for e in known_entities(source) if e not in args]
        if dropped:
            return None, f"rejected: unfaithful — sentence mentions {','.join(dropped)} but proposal drops it"
    bad = [(a, d) for a, d in zip(args, SCHEMAS[pred]) if not _domain_ok(d, a, source_tokens)]
    if bad:
        return None, "rejected: type mismatch — " + ", ".join(f"{a} is not {d}" for a, d in bad)
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
    bound = set()
    for i, (pred, args) in enumerate(r.body):
        if pred in BUILTINS:
            if len(args) != 2:
                return None, f"rejected: {pred} builtin arity"
            unbound = [a for a in args if is_var(a) and a not in bound]
            if unbound:
                return None, "rejected: builtin variables must be bound first: " + ",".join(unbound)
            continue
        if pred not in SCHEMAS:
            return None, f"rejected: unknown predicate '{pred}'"
        if len(args) != _arity(pred):
            return None, f"rejected: {pred} arity"
        bound |= {t for t in args if is_var(t)}
    pred, args = r.head
    if pred not in SCHEMAS:
        return None, f"rejected: unknown predicate '{pred}'"
    if len(args) != _arity(pred):
        return None, f"rejected: {pred} arity"
    if any(r.text == x.text for x in rules):
        return None, "duplicate: rule already known"
    head_vars = {t for t in r.head[1] if t[:1].isupper()}
    body_vars = {t for a in r.body for t in a[1] if t[:1].isupper()}
    if not head_vars <= body_vars:
        return None, "rejected: unbound variable in head"
    return r, "verified"
