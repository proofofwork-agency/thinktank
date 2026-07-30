from __future__ import annotations

from rapana.secrets import SecretsProvider, get_secrets_provider


def get_keys() -> dict[str, str]:
    """Return MEXC API credentials from the configured secrets provider.

    Raises if keys are missing/empty. The provider is env-backed by default and
    vault-upgradeable — swap the implementation in rapana.secrets without
    touching consumers.
    """
    provider: SecretsProvider = get_secrets_provider()
    key = provider.get("MEXC_API_KEY")
    secret = provider.get("MEXC_API_SECRET")
    if not key or not secret:
        raise RuntimeError(
            "MEXC API key/secret not found. Set MEXC_API_KEY and MEXC_API_SECRET "
            "in your environment or .env (read-only key, NO withdraw permission)."
        )
    return {"apiKey": key, "secret": secret}
