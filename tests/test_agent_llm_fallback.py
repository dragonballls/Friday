import agent.llm as llm


class _PrimaryPartialThenFails:
    def chat(self, messages, tools=None):
        yield {"type": "tokens", "content": "partial"}
        yield {"type": "error", "error": "429 rate limit"}


class _PrimaryFails:
    def chat(self, messages, tools=None):
        yield {"type": "error", "error": "429 rate limit"}


class _PrimaryNormalTextMentionsTimeout:
    def chat(self, messages, tools=None):
        yield {"type": "done", "content": "A timeout is a useful failure mode to handle.", "tool_calls": None}


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
    monkeypatch.setattr(llm, "_provider", _PrimaryPartialThenFails())
    monkeypatch.setattr(llm, "_provider_name", "openrouter")
    monkeypatch.setattr(llm, "_get_fallback_provider", lambda name: (_Fallback(), "ollama"))

    events = list(llm.chat([]))

    assert [event["type"] for event in events] == ["tokens", "error"]


def test_normal_completed_text_does_not_trigger_fallback(monkeypatch):
    monkeypatch.setattr(llm, "_provider", _PrimaryNormalTextMentionsTimeout())
    monkeypatch.setattr(llm, "_provider_name", "openrouter")
    monkeypatch.setattr(llm, "_get_fallback_provider", lambda name: (_Fallback(), "ollama"))

    events = list(llm.chat([]))

    assert len(events) == 1
    assert events[0]["content"].startswith("A timeout")
