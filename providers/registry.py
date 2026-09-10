"""Provider registration and eligibility lookup."""

from __future__ import annotations

from providers.policy import assert_provider_allowed

_PROVIDER_REGISTRY: dict[str, type] = {}


def register_provider(name: str, cls: type) -> None:
    _PROVIDER_REGISTRY[name.strip().lower()] = cls


def get_provider_class(name: str, *, cloud_hosted: bool | None = None) -> type:
    normalized = name.strip().lower()
    cls = _PROVIDER_REGISTRY.get(normalized)
    if cls is None:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {list(_PROVIDER_REGISTRY.keys())}"
        )
    assert_provider_allowed(normalized, cloud_hosted=cloud_hosted)
    return cls


def list_providers(*, eligible_only: bool = False, cloud_hosted: bool | None = None) -> list[str]:
    if not eligible_only:
        return list(_PROVIDER_REGISTRY.keys())
    return [
        name
        for name in _PROVIDER_REGISTRY
        if _provider_is_eligible(name, cloud_hosted=cloud_hosted)
    ]


def _provider_is_eligible(name: str, *, cloud_hosted: bool | None) -> bool:
    try:
        assert_provider_allowed(name, cloud_hosted=cloud_hosted)
    except PermissionError:
        return False
    return True
