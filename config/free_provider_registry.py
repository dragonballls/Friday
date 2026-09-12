"""Declarative catalog of AI routes Jarvis may use under free-only policy.

This registry is deliberately data-only. Jarvis never creates accounts, adds
billing details, buys credits, or follows arbitrary remote instructions.
"""

from __future__ import annotations

from typing import Any

FREE_PROVIDER_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "name": "openrouter",
        "display_name": "OpenRouter Free Models Router",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/free",
        "credential_env": "OPENROUTER_API_KEY",
        "requires_user_credential": True,
        "free_only": True,
        "source": "https://openrouter.ai/openrouter/free/",
    },
)


def get_free_provider_registry() -> list[dict[str, Any]]:
    """Return a copy so callers cannot mutate the built-in catalog."""
    return [dict(item) for item in FREE_PROVIDER_REGISTRY]


def get_free_provider(name: str) -> dict[str, Any] | None:
    for item in FREE_PROVIDER_REGISTRY:
        if item["name"] == name:
            return dict(item)
    return None
