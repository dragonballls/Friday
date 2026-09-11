from config.providers import get_active_provider


def test_legacy_local_default_never_wins_over_configured_cloud_primary():
    config = {
        "default": {"provider": "local"},
        "routing": {"primary": "openai"},
        "openai": {"api_key": "test-key"},
    }

    assert get_active_provider(config) == "openai"


def test_configured_cloud_default_remains_authoritative_without_primary():
    config = {
        "default": {"provider": "openrouter"},
        "routing": {"primary": ""},
        "openrouter": {"api_key": "test-key"},
        "openai": {"api_key": "test-key"},
    }

    assert get_active_provider(config) == "openrouter"


def test_configured_routing_primary_wins_when_default_is_missing():
    config = {
        "routing": {"primary": "openai"},
        "openai": {"api_key": "test-key"},
    }

    assert get_active_provider(config) == "openai"


def test_local_default_falls_back_to_configured_cloud():
    config = {
        "default": {"provider": "local"},
        "routing": {},
        "gemini": {"api_key": "test-key"},
    }

    assert get_active_provider(config) == "gemini"
