"""Build the action-prediction training set from verified experience.

Each example is (state_context -> verified_action): the action a verifier blessed
given the task state. Real traces come from the ExperienceLedger + EvidenceStore;
a deterministic synthetic generator adds trainable volume, since a live run yields
only hundreds of steps (see the v0.3 plan, open question O6).

Pure Python (no torch) so it is cheap to test. train_actions.py consumes the
(context, action) pairs in exactly the (sentence, logic) shape the NL->logic
trainer already uses.
"""

from ultrabrain.actions import ACTIONS, action_for_step, example, render_state


def from_ledger(ledger, evidence=None):
    """(context, action) pairs from recorded episodes + their verified outcomes.

    The memory snapshot is taken from each episode's own context (what was trusted
    at the time of the step), not the current store, so the example reflects the
    state the agent actually faced.
    """
    episodes = {e["id"]: e for e in ledger.read("episodes")}
    failures_by_ep = {}
    for f in ledger.read("failures"):
        if f.get("artifact"):
            failures_by_ep.setdefault(f.get("episode_id"), []).append(f["artifact"])
    pairs = []
    for row in ledger.read("actions"):
        ep = episodes.get(row.get("episode_id"))
        if not ep:
            continue
        kind = (row.get("action") or {}).get("kind")
        proved = row.get("accepted") if kind == "ask" else None
        action = action_for_step(kind, accepted=row.get("accepted", False), proved=proved)
        if action is None:
            continue
        ctx = ep.get("context") or {}
        beliefs = ctx.get("trusted_facts") or []
        pairs.append(example(ep["goal"], action, beliefs=beliefs,
                             failures=failures_by_ep.get(ep["id"], [])))
    return pairs


# --- deterministic synthetic augmenter ---------------------------------------
# Templated so it is reproducible (no RNG): each template names the verified
# action for a class of states, filled from fixed entity pools.

_PEOPLE = ["maria", "jan", "sofia", "lucas", "emma", "noah", "liam", "olivia"]
_CITIES = ["amsterdam", "paris", "berlin", "madrid", "rome", "lisbon"]
_COUNTRIES = ["netherlands", "france", "germany", "spain", "italy", "portugal"]
_MODULES = ["os", "sys", "json", "payment", "auth", "billing", "scheduler"]
_EQUATIONS = ["2*x + 3 = 11", "x/2 + 3 = 5", "5*x - 2 = 13", "x + 7 = 12"]


def _cycle(seq, i):
    return seq[i % len(seq)]


def synthetic(n=600):
    """~n diverse (state, action) pairs covering every action deterministically."""
    out = []
    i = 0
    while len(out) < n:
        p, p2 = _cycle(_PEOPLE, i), _cycle(_PEOPLE, i + 3)
        city, country = _cycle(_CITIES, i), _cycle(_COUNTRIES, i)
        mod, eq = _cycle(_MODULES, i), _cycle(_EQUATIONS, i)
        out.extend([
            example(f"solve {eq}", "call_oracle_math"),
            example(f"tell capital({country},{city})", "store_belief"),
            example(f"tell capital({country},{_cycle(_CITIES, i + 1)})", "reject_claim",
                    beliefs=[f"capital({country},{city})"]),
            example(f"ask grandparent({p},Z)", "answer",
                    beliefs=[f"parent({p},{p2})", f"parent({p2},{_cycle(_PEOPLE, i + 5)})"]),
            example(f"ask capital({country},X)", "retrieve_memory"),
            example("do the tests pass in this repo", "run_test"),
            example("which files changed since the last commit", "run_git_diff"),
            example(f"does module {mod} import cleanly", "run_import_check"),
            example(f"learn grandparent(X,Z) :- parent(X,Y), parent(Y,Z)", "write_proof_step"),
            example(f"translate this ambiguous sentence about {p}", "ask_teacher"),
            example(f"the value for {country} is wrong and must be removed", "retract_belief",
                    beliefs=[f"capital({country},{city})"]),
        ])
        i += 1
    return out[:n]


def build_dataset(ledger=None, evidence=None, synthetic_n=600, holdout_every=10):
    """Real (if given) + synthetic pairs, split deterministically into train/holdout."""
    pairs = []
    if ledger is not None:
        pairs += from_ledger(ledger, evidence)
    pairs += synthetic(synthetic_n)
    holdout = [p for i, p in enumerate(pairs) if i % holdout_every == 0]
    train = [p for i, p in enumerate(pairs) if i % holdout_every != 0]
    return train, holdout


def export(pairs, path):
    import json
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for ctx, action in pairs:
            f.write(json.dumps({"context": ctx, "action": action}, sort_keys=True) + "\n")
    return path
