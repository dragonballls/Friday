"""Provider eligibility policy for Friday.

Provider registration is intentionally separate from provider eligibility. A
provider can exist in the codebase while still being forbidden as an execution
backend. Local inference is disabled by policy so Friday cannot silently fall
back to Ollama or another machine-hosted model.
"""

from __future__ import annotations

LOCAL_INFERENCE_PROVIDERS = frozenset({"ollama"})


def is_provider_allowed(name: str, *, cloud_hosted: bool | None = None) -> bool:
    """Return whether a provider is eligible for Friday's model runtime.

    Local inference is always rejected. For other providers, callers must
    explicitly establish cloud hosting before this policy returns True.
    """
    normalized = name.strip().lower()
    if not normalized or normalized in LOCAL_INFERENCE_PROVIDERS:
        return False
    return cloud_hosted is True


def assert_provider_allowed(name: str, *, cloud_hosted: bool | None = None) -> None:
    if not is_provider_allowed(name, cloud_hosted=cloud_hosted):
        raise PermissionError(
            f"Provider '{name}' is not eligible for Friday: "
            "local inference is disabled and cloud eligibility must be explicit."
        )
