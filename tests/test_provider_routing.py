from config.providers import get_active_provider


def test_legacy_ollama_default_is_forced_to_free_route():
    config = {
        "default": {"provider": "ollama"},
        "routing": {"primary": "openai"},
    }

    assert get_active_provider(config) == "openrouter"


def test_explicit_remote_default_is_forced_to_free_route():
    config = {
        "default": {"provider": "openrouter"},
        "routing": {"primary": "openai"},
    }

    assert get_active_provider(config) == "openrouter"


def test_missing_default_is_forced_to_free_route():
    config = {"routing": {"primary": "openai"}}

    assert get_active_provider(config) == "openrouter"
