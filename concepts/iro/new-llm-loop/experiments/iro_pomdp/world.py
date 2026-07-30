"""Minimal partial-obs grid world for IRO v0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

Pos = Tuple[int, int]

# Actions
MOVE = {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}
LOOK = "LOOK"
ACTIONS = list(MOVE.keys()) + [LOOK]


@dataclass
class WorldConfig:
    width: int = 7
    height: int = 7
    fov: int = 0  # blind walk: passive obs only self; LOOK required to see
    look_radius: int = 2
    max_steps: int = 100
    # Close door after first LOOK can commit free geometry, but before agents cross.
    # (Prior shift_at=10 fired after the east-side transit → no_verify never hurt.)
    shift_at: Optional[int] = 4
    seed: int = 0


@dataclass
class World:
    cfg: WorldConfig
    walls: Set[Pos]
    goal: Pos
    agent: Pos
    t: int = 0
    shift_done: bool = False
    true_map: Dict[Pos, str] = field(default_factory=dict)

    @classmethod
    def make(cls, cfg: WorldConfig | None = None) -> "World":
        cfg = cfg or WorldConfig()
        # Border walls + one internal wall segment with a "door" gap
        walls: Set[Pos] = set()
        for x in range(cfg.width):
            walls.add((x, 0))
            walls.add((x, cfg.height - 1))
        for y in range(cfg.height):
            walls.add((0, y))
            walls.add((cfg.width - 1, y))
        # Vertical barrier at x=3 with gap at y=3 (door)
        for y in range(1, cfg.height - 1):
            if y != 3:
                walls.add((3, y))
        agent = (1, 1)
        goal = (cfg.width - 2, cfg.height - 2)
        w = cls(cfg=cfg, walls=walls, goal=goal, agent=agent)
        w._rebuild_map()
        return w

    def _rebuild_map(self) -> None:
        self.true_map = {}
        for y in range(self.cfg.height):
            for x in range(self.cfg.width):
                p = (x, y)
                if p == self.goal:
                    self.true_map[p] = "G"
                elif p in self.walls:
                    self.true_map[p] = "#"
                else:
                    self.true_map[p] = "."

    def in_bounds(self, p: Pos) -> bool:
        x, y = p
        return 0 <= x < self.cfg.width and 0 <= y < self.cfg.height

    def free(self, p: Pos) -> bool:
        return self.in_bounds(p) and p not in self.walls

    def observe(self, radius: int) -> Dict[Pos, str]:
        """Local observation relative to agent (absolute coords keys)."""
        ax, ay = self.agent
        obs: Dict[Pos, str] = {}
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                p = (ax + dx, ay + dy)
                if not self.in_bounds(p):
                    obs[p] = "#"
                elif p == self.agent:
                    obs[p] = "A"
                else:
                    obs[p] = self.true_map[p]
        return obs

    def passive_obs(self) -> Dict[Pos, str]:
        return self.observe(self.cfg.fov)

    def look_obs(self) -> Dict[Pos, str]:
        return self.observe(self.cfg.look_radius)

    def maybe_shift(self) -> bool:
        """Move the door: close y=3 gap, open y=5 instead.

        Also seals a short west-side spur at (2,3) so agents that already
        committed free corridor geometry face a second false-free trap without
        external re-verify.
        """
        if self.shift_done or self.cfg.shift_at is None:
            return False
        if self.t < self.cfg.shift_at:
            return False
        # Close old door, open new (longer detour)
        self.walls.add((3, 3))
        self.walls.discard((3, 5))
        # Trap: previously free cell on approach becomes wall (stale free hurts no_verify)
        self.walls.add((2, 3))
        self._rebuild_map()
        self.shift_done = True
        return True

    def step(self, action: str) -> Tuple[Dict[Pos, str], float, bool, dict]:
        """
        Apply action. Returns (obs, reward, done, info).
        LOOK does not move; MOVE attempts displacement.
        """
        info = {
            "action": action,
            "shifted": False,
            "blocked": False,
            "look": action == LOOK,
            "agent": self.agent,
            "goal": self.goal,
        }
        reward = -0.01  # step cost
        if action == LOOK:
            reward -= 0.05  # sensing cost
            obs = self.look_obs()
        elif action in MOVE:
            dx, dy = MOVE[action]
            nxt = (self.agent[0] + dx, self.agent[1] + dy)
            if self.free(nxt):
                self.agent = nxt
            else:
                info["blocked"] = True
                reward -= 0.02
            obs = self.passive_obs()
        else:
            raise ValueError(f"unknown action {action}")

        self.t += 1
        if self.maybe_shift():
            info["shifted"] = True
            # After shift, re-observe with same mode radius
            r = self.cfg.look_radius if action == LOOK else self.cfg.fov
            obs = self.observe(r)

        done = self.agent == self.goal or self.t >= self.cfg.max_steps
        if self.agent == self.goal:
            reward += 1.0
        info["agent"] = self.agent
        return obs, reward, done, info

    def verify_move(self, from_p: Pos, to_p: Pos, claimed_free: bool) -> bool:
        """External verifier: was the transition physically legal?"""
        if to_p == from_p:
            return True  # stayed
        dx = abs(to_p[0] - from_p[0]) + abs(to_p[1] - from_p[1])
        if dx != 1:
            return False
        actually_free = self.free(to_p) or to_p == self.agent
        # After move, agent is on to_p if free; if blocked, agent still from_p
        if claimed_free:
            return actually_free or to_p == self.agent
        return not self.free(to_p)

    def cell_truth(self, p: Pos) -> str:
        if p == self.goal:
            return "G"
        if p in self.walls:
            return "#"
        return "."
