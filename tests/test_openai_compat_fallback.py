import pytest

from providers.openai_compat import OpenAICompatibleProvider


def test_retryable_primary_failure_uses_configured_fallback():
    provider = OpenAICompatibleProvider(
        {
            "model": "primary-model",
            "fallback_model": "fallback-model",
        }
    )
    attempts = []

    def fake_stream(model, *args):
        attempts.append(model)
        if model == "primary-model":
            raise RuntimeError("429 rate limit")
        yield {"type": "done", "content": "fallback response", "tool_calls": None}

    provider._stream = fake_stream

    events = list(provider.chat([], tools=[]))

    assert attempts == ["primary-model", "fallback-model"]
    assert events == [
        {"type": "done", "content": "fallback response", "tool_calls": None}
    ]


def test_non_retryable_failure_does_not_use_fallback():
    provider = OpenAICompatibleProvider(
        {
            "model": "primary-model",
            "fallback_model": "fallback-model",
        }
    )
    attempts = []

    def fake_stream(model, *args):
        attempts.append(model)
        raise RuntimeError("401 invalid API key")
        yield  # pragma: no cover

    provider._stream = fake_stream

    events = list(provider.chat([]))

    assert attempts == ["primary-model"]
    assert events[0]["type"] == "error"
    assert "401 invalid API key" in events[0]["error"]


def test_partial_primary_stream_is_not_duplicated_by_fallback():
    provider = OpenAICompatibleProvider(
        {
            "model": "primary-model",
            "fallback_model": "fallback-model",
        }
    )
    attempts = []

    def fake_stream(model, *args):
        attempts.append(model)
        yield {"type": "tokens", "content": "partial"}
        raise RuntimeError("timeout")

    provider._stream = fake_stream

    events = list(provider.chat([]))

    assert attempts == ["primary-model"]
    assert events[0] == {"type": "tokens", "content": "partial"}
    assert events[1]["type"] == "error"
    assert "timeout" in events[1]["error"]
