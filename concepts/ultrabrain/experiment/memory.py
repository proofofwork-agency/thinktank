"""Shared memory interface for the decisive A/B experiment.

Both systems use the same teacher and tool runners. The memory implementation is
the only variable under test: System A uses a simple vector store, while System B
uses UltraBrain evidence, beliefs, and provenance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    @abstractmethod
    def remember(self, episode: dict[str, Any]) -> None:
        """Store one interaction, including task, actions, oracle result, and claims."""

    @abstractmethod
    def recall(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return context for the agent prompt: {"text": str, "tokens": int}."""

    @abstractmethod
    def trusted_writes(self) -> list[dict[str, Any]]:
        """Return claims the memory currently treats as trusted."""

    @abstractmethod
    def provenance_for(self, claim: str) -> dict[str, Any] | None:
        """Return provenance for a claim, or None if the claim is unknown."""
