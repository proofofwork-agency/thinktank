"""IRO Priority-A agent and ablations for the toy POMDP."""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from world import ACTIONS, LOOK, MOVE, Pos, World

Cell = str


@dataclass
class LedgerEntry:
    cell: Cell
    conf: float
    source: str


@dataclass
class EpisodeStats:
    success: bool = False
    steps: int = 0
    looks: int = 0
    false_commits: int = 0
    commits: int = 0
    rollbacks: int = 0
    recoveries_after_shift: int = 0
    shifted: bool = False
    reward: float = 0.0
    mode: str = ""


@dataclass
class Belief:
    cells: Dict[Pos, LedgerEntry] = field(default_factory=dict)
    agent: Optional[Pos] = None

    def get(self, p: Pos) -> Cell:
        e = self.cells.get(p)
        return e.cell if e else "?"

    def conf(self, p: Pos) -> float:
        e = self.cells.get(p)
        return e.conf if e else 0.0


class IROAgent:
    def __init__(self, mode: str = "full", rng: Optional[random.Random] = None):
        self.mode = mode
        self.rng = rng or random.Random(0)
        self.belief = Belief()
        self.stats = EpisodeStats(mode=mode)
        self._post_shift_steps = 0
        self._seen_shift = False
        self._steps_since_look = 99
        self._last_look_ig = 0.0

    def reset(self) -> None:
        self.belief = Belief()
        self.stats = EpisodeStats(mode=self.mode)
        self._post_shift_steps = 0
        self._seen_shift = False
        self._steps_since_look = 99
        self._last_look_ig = 0.0

    def _predict_obs(self, world_agent: Pos, radius: int) -> Dict[Pos, str]:
        pred: Dict[Pos, str] = {}
        ax, ay = world_agent
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                p = (ax + dx, ay + dy)
                if p == world_agent:
                    pred[p] = "A"
                else:
                    pred[p] = self.belief.get(p)
        return pred

    def eyes_update(self, obs: Dict[Pos, str], radius: int, force_all: bool = False) -> float:
        if self.belief.agent is None:
            for p, v in obs.items():
                if v == "A":
                    self.belief.agent = p
        pred = self._predict_obs(self.belief.agent or (0, 0), radius)
        surprise = 0.0
        for p, o in obs.items():
            if o == "A":
                self.belief.agent = p
                continue
            expected = pred.get(p, "?")
            conf = self.belief.conf(p)
            existing = self.belief.cells.get(p)

            # no_verify pathology: sticky unverified commits refuse sensory revision.
            # Without external verify, ledger "facts" win over the world after shift/traps.
            if (
                self.mode == "no_verify"
                and existing is not None
                and existing.source == "commit"
                and existing.conf >= 0.8
                and existing.cell != o
                and not force_all
            ):
                surprise += 1.0  # anomaly logged but not integrated
                continue

            if expected == "?" or force_all or self.mode == "no_eyes":
                pe, precision = 1.0, 1.0
            else:
                pe = 0.0 if expected == o else 1.0
                precision = 0.3 + 0.7 * conf
            s = precision * pe
            surprise += s
            # Anomaly channel: PE always eligible; gate only "how hard we revise"
            if pe > 0 or expected == "?" or force_all or self.mode == "no_eyes":
                if expected not in ("?", o) and conf > 0.5:
                    self.stats.rollbacks += 1
                self.belief.cells[p] = LedgerEntry(cell=o, conf=min(1.0, max(conf, 0.5) + 0.35), source="eyes")
            elif pe == 0 and expected == o:
                self.belief.cells[p] = LedgerEntry(cell=o, conf=min(1.0, conf + 0.05), source="eyes")

            # no_verify: promote free/goal obs into high-conf commits *without* external check.
            # After mid-episode door shift those commits become false sticky geometry.
            if self.mode == "no_verify" and o in (".", "G"):
                self.belief.cells[p] = LedgerEntry(cell=o, conf=0.95, source="commit")
                self.stats.commits += 1
        return surprise

    def _unknown_near(self, world: World, radius: int = 3) -> List[Pos]:
        if not self.belief.agent:
            return []
        ax, ay = self.belief.agent
        out: List[Pos] = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                p = (ax + dx, ay + dy)
                if world.in_bounds(p) and self.belief.get(p) == "?":
                    out.append(p)
        return out

    def _expected_info_gain(self, world: World) -> float:
        """How many unknown cells LOOK would cover (proxy for E[ΔH])."""
        unknowns = self._unknown_near(world, radius=4)
        if not unknowns or not self.belief.agent:
            return 0.0
        ax, ay = self.belief.agent
        r = world.cfg.look_radius
        covered = sum(1 for p in unknowns if abs(p[0] - ax) <= r and abs(p[1] - ay) <= r)
        return float(covered)

    def _goal_pos(self) -> Optional[Pos]:
        for p, e in self.belief.cells.items():
            if e.cell == "G":
                return p
        return None

    def _passable_belief(self, p: Pos) -> bool:
        c = self.belief.get(p)
        return c in (".", "G", "?", "A")

    def _bfs_next(self, world: World, target: Pos) -> Optional[str]:
        if not self.belief.agent:
            return None
        start = self.belief.agent
        if start == target:
            return None
        q = deque([start])
        prev: Dict[Pos, Optional[Pos]] = {start: None}
        found = False
        while q:
            cur = q.popleft()
            if cur == target:
                found = True
                break
            for a, (dx, dy) in MOVE.items():
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in prev or not world.in_bounds(nxt):
                    continue
                if not self._passable_belief(nxt):
                    continue
                # do not path through known walls
                if self.belief.get(nxt) == "#":
                    continue
                prev[nxt] = cur
                q.append(nxt)
        if not found:
            return None
        # walk back
        cur = target
        while prev[cur] is not None and prev[cur] != start:
            cur = prev[cur]
        # cur is first step
        sx, sy = start
        tx, ty = cur
        for a, (dx, dy) in MOVE.items():
            if (sx + dx, sy + dy) == (tx, ty):
                return a
        return None

    def _greedy_move(self, world: World) -> str:
        goal = self._goal_pos()
        if not self.belief.agent:
            return self.rng.choice(list(MOVE.keys()))
        ax, ay = self.belief.agent
        # Prefer BFS to known goal
        if goal is not None:
            step = self._bfs_next(world, goal)
            if step:
                return step
        # Else BFS toward nearest unknown (explore)
        unknowns = self._unknown_near(world, radius=5)
        if unknowns:
            unknowns.sort(key=lambda p: abs(p[0] - ax) + abs(p[1] - ay))
            for u in unknowns[:8]:
                step = self._bfs_next(world, u)
                if step:
                    return step
        # Local try: any non-wall neighbor
        opts = []
        for a, (dx, dy) in MOVE.items():
            nxt = (ax + dx, ay + dy)
            if self.belief.get(nxt) != "#":
                opts.append(a)
        return self.rng.choice(opts) if opts else self.rng.choice(list(MOVE.keys()))

    def select_action(self, world: World) -> str:
        mode = self.mode
        self._steps_since_look += 1

        if mode == "random_sense":
            return LOOK if self.rng.random() < 0.3 else self.rng.choice(list(MOVE.keys()))

        if mode == "never_look":
            return self._greedy_move(world)

        if mode == "always_look":
            # look periodically but still move
            if self._steps_since_look >= 2 and self._unknown_near(world):
                return LOOK
            return self._greedy_move(world)

        if mode == "no_search":
            return self.rng.choice(ACTIONS)

        # full / no_eyes / no_verify — info-gain Search (interleaved; never look-lock)
        e_ig = self._expected_info_gain(world)
        need_reacquire = self._seen_shift and self._steps_since_look >= 2
        # LOOK when expected coverage is worth cost and we moved at least once since last look
        if self._steps_since_look >= 2 and (e_ig >= 2.0 or need_reacquire):
            return LOOK
        # If completely dark (no adjacent knowledge), one LOOK is mandatory
        if self.belief.agent:
            ax, ay = self.belief.agent
            adj_known = any(
                self.belief.get((ax + dx, ay + dy)) != "?"
                for dx, dy in MOVE.values()
            )
            if not adj_known and self._steps_since_look >= 1:
                return LOOK
        return self._greedy_move(world)

    def run_commit(self, world: World, action: str, info: dict, prev_agent: Pos) -> None:
        new_agent = info["agent"]

        if self.mode == "no_verify":
            # Open-loop Run: commit *intent* / prediction, never call external verifier.
            # On collision: still mark target free (false geometry) and never write walls.
            self.belief.agent = new_agent
            if action in MOVE:
                dx, dy = MOVE[action]
                tgt = (prev_agent[0] + dx, prev_agent[1] + dy)
                if info.get("blocked"):
                    self.belief.cells[tgt] = LedgerEntry(".", 0.95, "commit")
                    self.stats.commits += 1
                    if world.cell_truth(tgt) == "#":
                        self.stats.false_commits += 1
                else:
                    cell = "G" if new_agent == world.goal else "."
                    self.belief.cells[new_agent] = LedgerEntry(cell, 0.95, "commit")
                    self.stats.commits += 1
                    if world.cell_truth(new_agent) == "#" or (
                        cell == "G" and new_agent != world.goal
                    ):
                        self.stats.false_commits += 1
            return

        if action in MOVE:
            dx, dy = MOVE[action]
            tgt = (prev_agent[0] + dx, prev_agent[1] + dy)
            if info.get("blocked"):
                # External verify: only commit wall if physics agrees
                if world.cell_truth(tgt) == "#":
                    self.belief.cells[tgt] = LedgerEntry("#", 1.0, "commit")
                    self.stats.commits += 1
                else:
                    self.stats.rollbacks += 1
            else:
                ok = world.verify_move(prev_agent, new_agent, claimed_free=True)
                if ok:
                    self.belief.agent = new_agent
                    self.belief.cells[new_agent] = LedgerEntry(
                        "G" if new_agent == world.goal else ".", 1.0, "commit"
                    )
                    self.stats.commits += 1
                else:
                    self.stats.rollbacks += 1
                    self.stats.false_commits += 1
        else:
            self.belief.agent = new_agent


def run_episode(mode: str, seed: int = 0, shift: bool = True) -> EpisodeStats:
    rng = random.Random(seed)
    from world import WorldConfig

    world = World.make(WorldConfig(seed=seed, shift_at=4 if shift else None))
    agent = IROAgent(mode=mode, rng=rng)
    agent.reset()

    obs = world.passive_obs()
    agent.eyes_update(obs, world.cfg.fov, force_all=True)
    agent.belief.agent = world.agent

    total_r = 0.0
    done = False
    while not done:
        prev = world.agent
        action = agent.select_action(world)
        if action == LOOK:
            agent.stats.looks += 1
            agent._steps_since_look = 0
        obs, r, done, info = world.step(action)
        total_r += r
        if info.get("shifted"):
            agent.stats.shifted = True
            agent._seen_shift = True
        radius = world.cfg.look_radius if action == LOOK else world.cfg.fov
        agent.eyes_update(obs, radius)
        agent.run_commit(world, action, info, prev)
        if agent._seen_shift and not done:
            agent._post_shift_steps += 1
            agent.stats.recoveries_after_shift = agent._post_shift_steps
        agent.stats.steps += 1

    agent.stats.success = world.agent == world.goal
    agent.stats.reward = total_r
    return agent.stats
