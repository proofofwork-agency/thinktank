"""Zero-ML proposers.

Slice 1 isolates the VERIFIER's value, so the "model" is a deterministic, deliberately-noisy
sampler over each task's ``{gold, distractor, mutation}`` pool. A distractor is crafted to pass the
weak (visible) tests but fail the hidden ones — the substrate experiment H2 needs to measure
false-certification. Seeded -> reproducible.
"""
from __future__ import annotations

import random

# (find, replace) edits that turn a correct program into a plausibly-buggy one.
_MUTATIONS = [
    ("==", "!="), (" + ", " - "), ("<=", "<"), (">=", ">"),
    (" and ", " or "), ("return True", "return False"), ("[0]", "[1]"),
]


def _mutate_code(src: str, rng: random.Random) -> str:
    rng.shuffle(candidates := list(_MUTATIONS))
    for find, repl in candidates:
        if find in src:
            return src.replace(find, repl, 1)
    return src


class NoisyProposer:
    """Per task, return ``n`` candidates sampled from the task's pool. Seeded by (task id, seed)."""

    def __init__(self, p_gold: float = 0.45, p_distractor: float = 0.35, seed: int = 0):
        self.p_gold = p_gold
        self.p_distractor = p_distractor
        self.seed = seed

    def propose(self, task: dict, n: int) -> list:
        rng = random.Random(f"{task.get('id')}:{self.seed}")
        gold = task["gold"]
        distractors = list(task.get("distractors", []))
        out = []
        for _ in range(n):
            r = rng.random()
            if r < self.p_gold:
                out.append(gold)
            elif r < self.p_gold + self.p_distractor and distractors:
                out.append(rng.choice(distractors))
            elif task.get("kind") == "code":
                out.append(_mutate_code(gold, rng))
            else:
                out.append(rng.choice(distractors) if distractors else gold)
        return out


class GoldProposer:
    """Control: always emits the reference solution."""

    def propose(self, task: dict, n: int) -> list:
        return [task["gold"]] * n
