import agent.llm as llm
from providers.openai_compat import OpenAICompatibleProvider
from providers.registry import get_provider_class


def test_zen_coder_provider_is_registered_for_diagnostics():
    assert get_provider_class("zen_coder") is OpenAICompatibleProvider


def test_named_zen_provider_is_blocked_by_free_only_policy(monkeypatch):
    monkeypatch.setattr(llm, "_provider_cache", {"zen_coder": object()})
    monkeypatch.setattr(llm, "_provider_has_credentials", lambda name: True)

    events = list(llm.chat([], provider_name="zen_coder"))

    assert events
    assert events[-1]["type"] == "error"
    assert "free" in events[-1]["content"].lower()


def test_missing_zen_credentials_do_not_use_unapproved_fallback(monkeypatch):
    monkeypatch.setattr(llm, "_provider_cache", {"openrouter": object()})
    monkeypatch.setattr(llm, "_provider_has_credentials", lambda name: False)
    monkeypatch.setattr(
        llm,
        "get_provider_config",
        lambda name=None: {"fallback_provider": "openrouter"} if name == "zen_coder" else {},
    )

    events = list(llm.chat([], provider_name="zen_coder"))

    assert events
    assert events[-1]["type"] == "error"
