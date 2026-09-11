import agent.llm as llm
from providers.openai_compat import OpenAICompatibleProvider
from providers.registry import get_provider_class


class _ZenProvider:
    def chat(self, messages, tools=None):
        yield {"type": "done", "content": "zen", "tool_calls": None}


class _Fallback:
    def chat(self, messages, tools=None):
        yield {"type": "done", "content": "fallback", "tool_calls": None}


def test_zen_coder_provider_is_registered():
    assert get_provider_class("zen_coder") is OpenAICompatibleProvider


def test_named_zen_provider_can_stream_without_touching_primary(monkeypatch):
    monkeypatch.setattr(llm, "_provider_cache", {"zen_coder": _ZenProvider()})
    monkeypatch.setattr(llm, "_provider_has_credentials", lambda name: name == "zen_coder")

    events = list(llm.chat([], provider_name="zen_coder"))

    assert events[-1]["content"] == "zen"


def test_missing_zen_credentials_use_configured_fallback(monkeypatch):
    monkeypatch.setattr(llm, "_provider_cache", {"openrouter": _Fallback()})
    monkeypatch.setattr(llm, "_provider_has_credentials", lambda name: name == "openrouter")
    monkeypatch.setattr(
        llm,
        "get_provider_config",
        lambda name=None: {"fallback_provider": "openrouter"} if name == "zen_coder" else {"api_key": "test-key"},
    )

    events = list(llm.chat([], provider_name="zen_coder"))

    assert any("switching to openrouter" in event.get("content", "") for event in events)
    assert events[-1]["content"] == "fallback"
