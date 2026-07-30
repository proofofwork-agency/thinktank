from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from rapana.config import get_settings


class SecretsProvider(ABC):
    """Abstract secrets provider. Default = environment; swap for Vault/AWS SM."""

    @abstractmethod
    def get(self, key: str) -> str | None: ...


class EnvSecretsProvider(SecretsProvider):
    """Reads secrets from a pydantic-settings env model (incl. .env file)."""

    def __init__(self) -> None:
        # BaseSettings loads from environment + .env automatically.
        self._settings = get_settings()

    def get(self, key: str) -> str | None:
        # pydantic-settings does not expose arbitrary keys directly; read from the
        # underlying os environment + .env via the model_config env file.
        import os

        value = os.environ.get(key)
        if value:
            return value
        # Fallback: parse the .env file manually for keys not on the Settings model.
        env_file = self._settings.model_config.get("env_file")
        if env_file:
            try:
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, _, v = line.partition("=")
                        if k.strip() == key:
                            return v.strip() or None
            except FileNotFoundError:
                pass
        return None


class StaticSecretsProvider(SecretsProvider):
    """In-memory provider for tests."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def get(self, key: str) -> str | None:
        return self._mapping.get(key)


_default_provider: SecretsProvider | None = None


def get_secrets_provider() -> SecretsProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = EnvSecretsProvider()
    return _default_provider


def set_secrets_provider(provider: SecretsProvider) -> None:
    """Inject a custom provider (used by tests / vault backends)."""
    global _default_provider
    _default_provider = provider


def reset_secrets_provider() -> None:
    global _default_provider
    _default_provider = None


def configure(provider: Any | None = None) -> None:
    """Re-export alias for ergonomic wiring."""
    if provider is not None:
        set_secrets_provider(provider)
