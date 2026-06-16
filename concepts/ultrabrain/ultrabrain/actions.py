"""Action vocabulary for the v0.3 action-prediction core.

The thesis (thoughts/23_beyond_token_prediction.md): instead of predicting the
next WORD, the neural core should predict the next VERIFIED ACTION given a task
state + memory context. The verifier/oracle layer then says whether that action
produced trusted memory — so the training signal is "actions a verifier blessed",
not raw text.

This module is pure Python (no torch): it defines the closed action set, maps a
recorded experience step + its verified outcome to the canonical action, renders
(state -> action) training examples in the same <S> ... <SEP> target <E> shape the
NL->logic trainer already uses, and parses a model's generated text back to an
action. A synthetic generator provides trainable volume (see data/action_traces.py).
"""

import re

# Closed action set. Each is a *verified next action* the agent can take; the
# model learns which one a verifier would bless given the current state.
ACTIONS = [
    "retrieve_memory",   # look up existing trusted beliefs / skills
    "run_test",          # run the pytest oracle
    "run_git_diff",      # run the git-diff oracle
    "run_import_check",  # run the import oracle
    "call_oracle_math",  # verify a math problem with the math oracle
    "write_proof_step",  # learn a rule / extend a derivation
    "ask_teacher",       # request a teacher proposal (untrusted until verified)
    "reject_claim",      # refuse an unsupported or contradictory claim
    "store_belief",      # commit a verified claim to trusted memory
    "retract_belief",    # retract a belief whose support is gone
    "answer",            # emit a proof-backed answer
]
ACTION_SET = set(ACTIONS)


def is_action(name):
    return name in ACTION_SET


# --- map a recorded experience step to the canonical verified action ----------
#
# An ExperienceLedger "actions" row carries action={"kind": ...} plus accepted,
# and (for ask) whether a proof was found. The verified-correct action is what a
# verifier would have blessed: a contradictory tell should have been a
# reject_claim, a valid one a store_belief, and so on.

def action_for_step(kind, accepted=False, proved=None):
    """Canonical action for a recorded step given its verified outcome."""
    if kind == "math":
        return "call_oracle_math"
    if kind == "tell":
        return "store_belief" if accepted else "reject_claim"
    if kind == "learn_rule":
        return "write_proof_step"
    if kind == "ask":
        return "answer" if proved else "retrieve_memory"
    if kind in ("oracle_pytest", "pytest", "run_test"):
        return "run_test"
    if kind in ("oracle_git_diff", "git", "git_diff", "run_git_diff"):
        return "run_git_diff"
    if kind in ("oracle_import", "import_check", "run_import_check"):
        return "run_import_check"
    if kind in ("teacher", "ask_teacher"):
        return "ask_teacher"
    if kind in ("retract", "retract_belief"):
        return "retract_belief"
    if kind in ("store_belief", "reject_claim", "answer", "retrieve_memory",
                "call_oracle_math", "write_proof_step"):
        return kind
    return None


# --- training-example rendering ----------------------------------------------
#
# A training example is (state_context, action). We reuse the NL->logic trainer's
# (sentence, logic) pair shape verbatim: the action string is the target emitted
# after <SEP>. Keeping the state compact matters — the whole UltraBrain bet is
# that memory lives outside the weights, so the context is a short snapshot.

def render_state(goal, beliefs=None, failures=None, max_beliefs=6, max_failures=3):
    """Render a compact state context string from a goal + memory snapshot."""
    parts = [f"task: {goal.strip()}"]
    bel = list(beliefs or [])[:max_beliefs]
    if bel:
        parts.append("memory: " + "; ".join(bel))
    fails = list(failures or [])[:max_failures]
    if fails:
        parts.append("failed: " + "; ".join(fails))
    return " | ".join(parts)


def example(goal, action, beliefs=None, failures=None):
    """One (state_context, action) training pair. Raises on an unknown action."""
    if action not in ACTION_SET:
        raise ValueError(f"unknown action: {action!r}")
    return render_state(goal, beliefs, failures), action


# --- parse a model's generated text back to an action ------------------------

def parse_action(text):
    """Map generated text to the nearest action. Exact match first, then a
    token-overlap fallback so a slightly noisy generation still resolves; None if
    nothing plausible matches (so the eval can count it as a miss, not a guess)."""
    t = (text or "").strip().lower()
    for a in ACTIONS:
        if t == a:
            return a
    toks = set(re.findall(r"[a-z_]+", t))
    best, best_score = None, 0
    for a in ACTIONS:
        score = len(toks & set(a.split("_")))
        if score > best_score:
            best, best_score = a, score
    return best if best_score > 0 else None
