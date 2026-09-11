from config import MAX_ITERATIONS, MODEL, get_system_prompt


class TestConfig:
    def test_model_is_cloud(self):
        assert MODEL == "cloud"

    def test_model_name(self):
        assert isinstance(MODEL, str)
        assert MODEL

    def test_max_iterations(self):
        assert MAX_ITERATIONS > 0

    def test_system_prompt_english(self):
        prompt = get_system_prompt("english")
        assert "USE TOOLS" in prompt

    def test_system_prompt_hinglish(self):
        prompt = get_system_prompt("hinglish")
        assert "USE KAR" in prompt or "TOOLS USE KAR" in prompt

    def test_system_prompt_default(self):
        prompt = get_system_prompt()
        assert len(prompt) > 100

    def test_provider_config(self):
        from config.providers import get_active_provider, get_provider_config

        provider = get_active_provider()
        assert provider in {"openrouter", "openai", "gemini", "deepseek", "zen_coder"}
        cfg = get_provider_config(provider)
        assert isinstance(cfg, dict)

    def test_provider_config_has_no_local_ai(self):
        from config.providers import load_provider_config

        cfg = load_provider_config()
        assert "ollama" not in cfg
        assert cfg["embeddings"]["engine"] == "tfidf"
