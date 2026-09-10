from config.providers import get_active_provider


def test_legacy_ollama_default_prefers_cloud_routing_primary():
    config = {
        "default": {"provider": "ollama"},
        "routing": {"primary": "openai"},
    }

    assert get_active_provider(config) == "openai"


def test_explicit_remote_default_remains_authoritative():
    config = {
        "default": {"provider": "openrouter"},
        "routing": {"primary": "openai"},
    }

    assert get_active_provider(config) == "openrouter"


def test_missing_default_uses_routing_primary():
    config = {"routing": {"primary": "openai"}}

    assert get_active_provider(config) == "openai"
