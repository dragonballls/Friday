from collections.abc import Generator

from providers import get_provider
from config.providers import get_provider_config


_provider = None
_provider_name = None


def _ensure_provider():
    global _provider, _provider_name

    if _provider is None:
        _provider = get_provider()
        _provider_name = getattr(_provider, "name", None) or "unknown"

    return _provider


def _is_retryable_provider_error(event: dict) -> bool:
    text = str(
        event.get("error")
        or event.get("content")
        or ""
    ).lower()

    retryable_markers = (
        "429",
        "rate limit",
        "rate_limit",
        "free-models-per-day",
        "timeout",
        "timed out",
        "connection",
        "connecterror",
        "connectionerror",
        "temporarily unavailable",
        "service unavailable",
        "502",
        "503",
        "504",
    )

    return any(marker in text for marker in retryable_markers)


def _get_fallback_provider():
    config = get_provider_config("openrouter")
    fallback_name = str(
        config.get("fallback_provider", "ollama")
    ).strip()

    if not fallback_name or fallback_name == "openrouter":
        return None, None

    try:
        provider = get_provider(fallback_name)
        return provider, fallback_name
    except Exception:
        return None, None


def _primary_failed(events: list[dict]) -> bool:
    for event in events:
        if event.get("type") == "error" and _is_retryable_provider_error(event):
            return True

        if event.get("type") == "done":
            if event.get("error") or _is_retryable_provider_error(event):
                return True

    return False


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> Generator[dict, None, None]:
    global _provider, _provider_name

    provider = _ensure_provider()
    provider_name = _provider_name or "unknown"

    primary_events = list(provider.chat(messages, tools=tools))

    if _primary_failed(primary_events):
        fallback, fallback_name = _get_fallback_provider()

        if fallback is not None:
            _provider = fallback
            _provider_name = fallback_name

            yield {
                "type": "tokens",
                "content": (
                    f"[{provider_name} unavailable; "
                    f"switching to {fallback_name}…]\n\n"
                ),
            }

            yield from fallback.chat(messages, tools=tools)
            return

    yield from primary_events

