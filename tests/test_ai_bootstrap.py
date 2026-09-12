import core.ai_bootstrap as bootstrap
from config.free_provider_registry import get_free_provider, get_free_provider_registry


def test_registry_contains_only_explicit_free_route():
    providers = get_free_provider_registry()
    assert providers
    assert all(item["free_only"] is True for item in providers)
    assert get_free_provider("openrouter")["model"] == "openrouter/free"
    assert get_free_provider("does_not_exist") is None


def test_discover_free_providers_reports_unconfigured_route(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "load_provider_config",
        lambda: {"openrouter": {"api_key": ""}},
    )
    providers = bootstrap.discover_free_providers()
    assert len(providers) == 1
    assert providers[0].name == "openrouter"
    assert providers[0].configured is False
    assert providers[0].free_only is True


def test_bootstrap_status_requires_one_time_setup(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "load_provider_config",
        lambda: {"openrouter": {"api_key": ""}},
    )
    status = bootstrap.bootstrap_status()
    assert status["ready"] is False
    assert status["requires_one_time_user_setup"] is True
    assert status["billing_allowed"] is False
    assert status["account_creation_allowed"] is False
    assert status["active_provider"] == "openrouter"


def test_bootstrap_status_reports_configured_route(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "load_provider_config",
        lambda: {"default": {"provider": "openrouter"}, "openrouter": {"api_key": "key"}},
    )
    status = bootstrap.bootstrap_status()
    assert status["ready"] is True
    assert status["requires_one_time_user_setup"] is False
    assert status["providers"][0]["configured"] is True


def test_validate_active_provider_requires_credential(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "discover_free_providers",
        lambda: [
            bootstrap.BootstrapProvider(
                name="openrouter",
                display_name="OpenRouter Free",
                model="openrouter/free",
                configured=False,
                credential_required=True,
                free_only=True,
                source="",
            )
        ],
    )
    monkeypatch.setattr(bootstrap, "get_provider_config", lambda name: {"api_key": ""})
    assert bootstrap.validate_active_provider() == (
        False,
        "A one-time AI credential is required before Jarvis can use cloud inference.",
    )


def test_validate_active_provider_accepts_configured_route(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "discover_free_providers",
        lambda: [
            bootstrap.BootstrapProvider(
                name="openrouter",
                display_name="OpenRouter Free",
                model="openrouter/free",
                configured=True,
                credential_required=True,
                free_only=True,
                source="",
            )
        ],
    )
    monkeypatch.setattr(bootstrap, "get_provider_config", lambda name: {"api_key": "key"})
    assert bootstrap.validate_active_provider() == (True, "openrouter")
