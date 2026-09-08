import agent.llm as llm


class _PrimaryPartialThenFails:
    def chat(self, messages, tools=None):
        yield {"type": "tokens", "content": "partial"}
        yield {"type": "error", "error": "429 rate limit"}


class _PrimaryFails:
    def chat(self, messages, tools=None):
        yield {"type": "error", "error": "429 rate limit"}


class _Fallback:
    def chat(self, messages, tools=None):
        yield {"type": "done", "content": "fallback", "tool_calls": None}


def test_partial_primary_output_does_not_trigger_duplicate_fallback(monkeypatch):
    monkeypatch.setattr(llm, "_provider", _PrimaryPartialThenFails())
    monkeypatch.setattr(llm, "_provider_name", "openrouter")
    monkeypatch.setattr(llm, "_get_fallback_provider", lambda name: (_Fallback(), "ollama"))

    events = list(llm.chat([]))

    assert [event["type"] for event in events] == ["tokens", "error"]
    assert events[0]["content"] == "partial"


def test_retryable_primary_failure_uses_fallback_when_nothing_was_emitted(monkeypatch):
    monkeypatch.setattr(llm, "_provider", _PrimaryFails())
    monkeypatch.setattr(llm, "_provider_name", "openrouter")
    monkeypatch.setattr(llm, "_get_fallback_provider", lambda name: (_Fallback(), "ollama"))

    events = list(llm.chat([]))

    assert any("switching to ollama" in event.get("content", "") for event in events)
    assert events[-1]["content"] == "fallback"
