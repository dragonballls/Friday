"""Jarvis free-only AI policy.

This module is intentionally conservative: Jarvis may use an AI endpoint only
when the selected configuration explicitly says it is free-only. It never
purchases credits, enables billing, upgrades a plan, or attempts to bypass
provider limits or verification.

Provider availability and free tiers change over time, so this policy does not
claim that a provider is permanently free. Instead, a provider must be marked
as currently free-only by configuration/discovery.
"""

from __future__ import annotations

import os
from typing import Any

FREE_ONLY_ENV = "JARVIS_FREE_ONLY"

# OpenRouter currently exposes a dedicated zero-price free-model router. The
# model is still subject to the provider's current limits and availability.
# This entry only identifies a safe default route; it does not create an
# account or credential.
KNOWN_FREE_ROUTES: dict[str, dict[str, str]] = {
    "openrouter": {"model": "openrouter/free"},
}


def free_only_enabled() -> bool:
    """Return whether Jarvis is operating under its mandatory free-only mode."""
    value = os.environ.get(FREE_ONLY_ENV, "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def provider_is_free_only(name: str, config: dict[str, Any]) -> bool:
    """Return True only when a provider is explicitly safe for free-only use."""
    if not free_only_enabled():
        return True

    if bool(config.get("free_only", False)):
        return True

    # The OpenRouter free router is a special case because the route itself is
    # explicitly priced at zero. Force its model below before use.
    return name in KNOWN_FREE_ROUTES and str(config.get("model", "")).strip() == KNOWN_FREE_ROUTES[name]["model"]


def enforce_free_provider(name: str, config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of provider config constrained to a free-only route.

    Raises ValueError instead of silently allowing a potentially billable
    endpoint. No billing, subscription, credit purchase, or limit bypass is
    ever attempted here.
    """
    safe = dict(config)
    if not free_only_enabled():
        return safe

    route = KNOWN_FREE_ROUTES.get(name)
    if route and name == "openrouter":
        safe["model"] = route["model"]
        safe["free_only"] = True

    if not provider_is_free_only(name, safe):
        raise ValueError(
            f"Provider '{name}' is blocked by Jarvis free-only policy. "
            "Jarvis will not enable billing, buy credits, upgrade a plan, "
            "bypass limits, or use a paid endpoint."
        )

    return safe


def free_provider_catalog() -> dict[str, dict[str, str]]:
    """Return the currently built-in free route catalog for discovery/UI code."""
    return {name: dict(route) for name, route in KNOWN_FREE_ROUTES.items()}
