"""Deterministic stdlib vector store for System A's memory baseline."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "what", "when", "where", "which", "who", "why", "with",
}


def _terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOPWORDS]


def _tf(text: str) -> Counter[str]:
    return Counter(_terms(text))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(weight * right.get(term, 0) for term, weight in left.items())
    if dot == 0:
        return 0.0
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    return dot / (left_norm * right_norm)


class VectorStore:
    def __init__(self):
        self._docs: dict[str, tuple[str, dict[str, Any], Counter[str]]] = {}

    def add(self, doc_id: str, text: str, meta: dict[str, Any] | None = None) -> None:
        self._docs[str(doc_id)] = (text, dict(meta or {}), _tf(text))

    def search(self, query: str, k: int = 5) -> list[tuple[float, str, str, dict[str, Any]]]:
        query_vec = _tf(query)
        if k <= 0 or not query_vec:
            return []
        hits = []
        for doc_id, (text, meta, vector) in self._docs.items():
            score = _cosine(query_vec, vector)
            if score > 0:
                hits.append((score, doc_id, text, dict(meta)))
        hits.sort(key=lambda hit: (-hit[0], hit[1]))
        return hits[:k]
