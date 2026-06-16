"""Search controller for verifier-grounded math generation.

The soundness boundary lives in generator.py: this module only chooses the
order in which already-closed operators are tried. A policy can affect search
efficiency, but every candidate still passes through the accept gate before it
can enter a certified trace.
"""

from __future__ import annotations

import heapq
from typing import Iterable, Protocol

from .generator import (
    Derivation,
    OPERATORS,
    SearchState,
    apply,
    goal_test,
    initial_state,
    solution_set_preserving,
)


class Policy(Protocol):
    name: str

    def propose(self, state: SearchState) -> Iterable[str]:
        """Return operator names in preferred expansion order."""

    def score(self, state: SearchState) -> float:
        """Higher scores are expanded first."""


class HeuristicPolicy:
    """Zero-ML policy for the one-variable linear domain."""

    name = "heuristic"
    order = ("swap_sides", "move_var", "move_const", "divide_by_coef")

    def propose(self, state: SearchState) -> list[str]:
        return [op for op in self.order if apply(op, state) is not None]

    def score(self, state: SearchState) -> float:
        if state.right is None:
            return 0.0 if state.left.coef == 0 else -1000.0
        penalty = abs(state.left.const) + abs(state.right.coef)
        if state.left.coef == 0:
            penalty += 10
        elif state.left.coef != 1:
            penalty += 1
        return -float(penalty)


def solve_search(
    problem: str,
    policy: Policy | None = None,
    *,
    max_nodes: int = 64,
    max_depth: int = 8,
    beam_width: int = 4,
) -> Derivation:
    """Search for a certified derivation, or abstain.

    The visited set is keyed by normalized equation state, not by trace, so
    loops cannot grow the frontier. ``beam_width`` limits how many verified
    children each expanded node contributes.
    """

    policy = policy or HeuristicPolicy()
    try:
        start = initial_state(problem)
    except ValueError:
        return Derivation(problem, False, (), None, 0, policy.name)

    frontier = []
    counter = 0
    visited = {start.key()}
    preservation_cache = {}
    heapq.heappush(frontier, (-policy.score(start), start.depth, start.text(), counter, start))
    nodes_expanded = 0

    while frontier and nodes_expanded < max_nodes:
        _score, _depth, _text, _counter, state = heapq.heappop(frontier)
        nodes_expanded += 1
        is_goal, answer = goal_test(state, problem)
        if is_goal:
            return Derivation(problem, True, state.trace, answer, nodes_expanded, policy.name)
        if state.depth >= max_depth:
            continue

        children = []
        for op in policy.propose(state):
            if op not in OPERATORS:
                continue
            cand = apply(op, state)
            if cand is None or cand.depth > max_depth:
                continue
            key = cand.key()
            if key in visited:
                continue
            ok = preservation_cache.get(key)
            if ok is None:
                ok = solution_set_preserving(cand, problem)
                preservation_cache[key] = ok
            if not ok:
                continue
            counter += 1
            children.append((-policy.score(cand), cand.depth, cand.text(), counter, cand))

        for item in sorted(children)[:beam_width]:
            visited.add(item[-1].key())
            heapq.heappush(frontier, item)

    return Derivation(problem, False, (), None, nodes_expanded, policy.name)
