import agent.llm as llm


def test_fallback_candidates_never_include_ollama(monkeypatch):
    config = {
        "openai": {"fallback_provider": "ollama"},
        "routing": {"fallback": ["ollama", "openrouter", "openrouter"]},
    }
    monkeypatch.setattr(llm, "load_provider_config", lambda: config)

    candidates = llm._provider_candidates_for_fallback("openai")

    assert "ollama" not in candidates
    assert candidates == ["openrouter"]


def test_unapproved_zen_fallback_is_skipped(monkeypatch):
    monkeypatch.setattr(
        llm,
        "load_provider_config",
        lambda: {
            "openai": {"fallback_provider": "openrouter"},
            "routing": {"fallback": ["zen_coder"]},
        },
    )
    monkeypatch.setattr(llm, "_get_named_provider", lambda name: object())
    monkeypatch.setattr(llm, "_provider_has_credentials", lambda name: name == "zen_coder")

    provider, name = llm._get_fallback_provider("openai")

    assert provider is None
    assert name is None


def test_retryable_provider_errors_are_limited_to_transient_failures():
    assert llm._is_retryable_provider_error({"type": "error", "error": "HTTP 503"})
    assert llm._is_retryable_provider_error({"type": "error", "error": "rate limit 429"})
    assert not llm._is_retryable_provider_error({"type": "error", "error": "invalid API key"})


def test_partial_output_prevents_duplicate_fallback(monkeypatch):
    class FakeProvider:
        name = "openai"

        def chat(self, messages, tools=None):
            yield {"type": "tokens", "content": "partial"}
            yield {"type": "error", "error": "503 service unavailable"}

    monkeypatch.setattr(llm, "_ensure_provider", lambda: FakeProvider())
    llm._provider_name = "openai"

    events = list(llm.chat([{"role": "user", "content": "hello"}]))

    assert [event.get("content") for event in events] == ["partial"]
