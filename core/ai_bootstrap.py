"""First-run AI bootstrap for Jarvis.

The bootstrap is intentionally non-destructive: it can discover and validate
configured free routes, but it never creates accounts, enters billing details,
purchases credits, or changes provider plans.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.free_ai_policy import enforce_free_provider
from config.free_provider_registry import get_free_provider_registry
from config.providers import get_provider_config, load_provider_config


@dataclass(frozen=True)
class BootstrapProvider:
    name: str
    display_name: str
    model: str
    configured: bool
    credential_required: bool
    free_only: bool
    source: str


def discover_free_providers() -> list[BootstrapProvider]:
    """Return only providers that are explicitly allowlisted as free-only."""
    config = load_provider_config()
    providers: list[BootstrapProvider] = []

    for entry in get_free_provider_registry():
        name = str(entry["name"])
        provider_cfg = config.get(name, {})
        if not isinstance(provider_cfg, dict):
            provider_cfg = {}

        try:
            safe_cfg = enforce_free_provider(name, provider_cfg)
        except (ValueError, KeyError, TypeError):
            continue

        providers.append(
            BootstrapProvider(
                name=name,
                display_name=str(entry["display_name"]),
                model=str(safe_cfg.get("model", entry["model"])),
                configured=bool(str(safe_cfg.get("api_key") or "").strip()),
                credential_required=bool(entry.get("requires_user_credential", True)),
                free_only=True,
                source=str(entry.get("source", "")),
            )
        )

    return providers


def bootstrap_status() -> dict[str, Any]:
    """Return safe first-run state suitable for the minimal Jarvis client."""
    config = load_provider_config()
    providers = discover_free_providers()
    configured = [item for item in providers if item.configured]

    try:
        default = config.get("default", {})
        active = str(default.get("provider", "")).strip() if isinstance(default, dict) else ""
    except (AttributeError, TypeError):
        active = ""

    if not active:
        active = "openrouter" if providers else (configured[0].name if configured else "")

    return {
        "ready": bool(configured),
        "active_provider": active,
        "providers": [
            {
                "name": item.name,
                "display_name": item.display_name,
                "model": item.model,
                "configured": item.configured,
                "credential_required": item.credential_required,
                "free_only": item.free_only,
                "source": item.source,
            }
            for item in providers
        ],
        "requires_one_time_user_setup": not bool(configured),
        "billing_allowed": False,
        "account_creation_allowed": False,
    }


def validate_active_provider() -> tuple[bool, str]:
    """Validate that the active route is still allowed before inference."""
    providers = discover_free_providers()
    if not providers:
        return False, "No free-only AI provider is currently configured."

    for provider in providers:
        try:
            cfg = get_provider_config(provider.name)
        except (ValueError, KeyError, TypeError) as exc:
            return False, str(exc)
        if str(cfg.get("api_key") or "").strip():
            return True, provider.name

    return False, "A one-time AI credential is required before Jarvis can use cloud inference."
