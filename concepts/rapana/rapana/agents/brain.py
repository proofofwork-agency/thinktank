from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Protocol

from rapana.logging import get_logger

log = get_logger(__name__)


class Brain(Protocol):
    """Optional reasoning brain for the Bull/Bear researchers.

    The brain only *annotates* debate theses (explanatory text). It never touches
    the numeric decision or the order path, so an LLM hallucination cannot cause
    a harmful trade — the deterministic combiner + risk gate decide everything.
    """

    def reason(self, prompt: str) -> str: ...


class DeterministicBrain:
    """Default brain: no LLM. Returns a short deterministic note.

    This keeps the fleet fully offline/testable. Configure RAPANA_LLM_PROVIDER
    (or pass an OpenAICompatibleBrain) for richer thesis prose (purely cosmetic).
    """

    name = "deterministic"

    def reason(self, prompt: str) -> str:
        return "deterministic analysis (no LLM)"


class CallableBrain:
    """Wrap any `fn(prompt) -> str` as a Brain (e.g. your own LLM client)."""

    def __init__(self, fn: Callable[[str], str], name: str = "callable") -> None:
        self._fn = fn
        self.name = name

    def reason(self, prompt: str) -> str:
        try:
            return str(self._fn(prompt))
        except Exception as exc:
            return f"(brain error: {exc})"


class OpenAICompatibleBrain:
    """LLM brain speaking the OpenAI Chat Completions API.

    Works with OpenAI, OpenRouter, Ollama (OpenAI compat), vLLM, LM Studio, etc.
    Fail-soft: any error becomes a short note string so the fleet never crashes
    on a flaky endpoint. Like DeterministicBrain, the output is purely cosmetic
    thesis prose — it cannot move a number or place an order.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        system: str | None = None,
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.system = system
        self.timeout = timeout
        self.name = "openai_compatible"

    def reason(self, prompt: str) -> str:
        messages: list[dict[str, str]] = []
        if self.system:
            messages.append({"role": "system", "content": self.system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.model, "messages": messages, "temperature": 0.2, "stream": False}
        try:
            data = json.dumps(body).encode("utf-8")
            headers = {"Content-Type": "application/json", "User-Agent": "rapana/1.0"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions", data=data, headers=headers,
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload["choices"][0]["message"]["content"].strip()
        except (OSError, KeyError, ValueError) as exc:
            return f"(brain error: {exc})"
        except Exception as exc:  # pragma: no cover - defensive catch-all
            return f"(brain error: {exc})"


def default_brain() -> Brain:
    return DeterministicBrain()


def build_brain(settings) -> Brain:
    """Build a Brain from Settings, defaulting to DeterministicBrain.

    The deterministic path stays the default and is used whenever the provider
    is unset, unrecognised, or misconfigured (e.g. missing key). An unknown
    provider is silently coerced to "none" so a typo never halts the fleet.
    """
    provider = getattr(settings, "llm_provider", "none").strip().lower()
    model = getattr(settings, "llm_model", None)
    base_url = getattr(settings, "llm_base_url", None)
    api_key = getattr(settings, "llm_api_key", None)

    if provider in {"none", "deterministic", ""}:
        return DeterministicBrain()

    if provider == "openrouter":
        if not api_key:
            log.warning("llm_brain_fallback_no_api_key", provider=provider)
            return DeterministicBrain()
        return OpenAICompatibleBrain(
            "https://openrouter.ai/api/v1", api_key, model or "openai/gpt-4o-mini"
        )

    if provider == "ollama":
        return OpenAICompatibleBrain(
            "http://localhost:11434/v1", api_key or "ollama", model or "llama3.1"
        )

    if provider == "openai":
        if not api_key:
            log.warning("llm_brain_fallback_no_api_key", provider=provider)
            return DeterministicBrain()
        return OpenAICompatibleBrain(
            "https://api.openai.com/v1", api_key, model or "gpt-4o-mini"
        )

    if provider in {"openai-compatible", "local"}:
        if not base_url:
            log.warning("llm_brain_fallback_no_base_url", provider=provider)
            return DeterministicBrain()
        return OpenAICompatibleBrain(base_url, api_key, model or "gpt-3.5-turbo")

    # Unknown provider: never crash the fleet, fall back to deterministic.
    return DeterministicBrain()
