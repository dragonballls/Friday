from collections.abc import Generator

from providers import get_provider
from config.providers import get_provider_config, load_provider_config


_provider = None
_provider_name = None
_provider_cache: dict[str, object] = {}


def _ensure_provider():
    global _provider, _provider_name

    if _provider is None:
        _provider = get_provider()
        _provider_name = getattr(_provider, "name", None) or "unknown"

    return _provider


def _get_named_provider(name: str):
    provider = _provider_cache.get(name)
    if provider is None:
        provider = get_provider(name)
        _provider_cache[name] = provider
    return provider


def _is_retryable_provider_error(event: dict) -> bool:
    text = str(event.get("error") or event.get("content") or "").lower()

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


def _provider_candidates_for_fallback(primary_name: str) -> list[str]:
    """Return cloud-first fallback candidates without forcing local inference."""
    config = load_provider_config()
    primary_config = config.get(primary_name, {})
    configured = str(primary_config.get("fallback_provider", "")).strip()

    candidates: list[str] = []
    if configured and configured != primary_name:
        candidates.append(configured)

    routing = config.get("routing", {})
    if isinstance(routing, dict):
        fallback_list = routing.get("fallback", [])
        if isinstance(fallback_list, str):
            fallback_list = [fallback_list]
        if isinstance(fallback_list, list):
            candidates.extend(str(item).strip() for item in fallback_list if str(item).strip())

    # Preserve cloud-first behavior when an older configuration still points
    # its fallback at Ollama. Prefer an already configured remote provider.
    if configured == "ollama":
        candidates.extend(("openai", "openrouter", "zen_coder"))

    seen: set[str] = set()
    return [
        name
        for name in candidates
        if name and name != primary_name and not (name in seen or seen.add(name))
    ]


def _get_fallback_provider(primary_name: str):
    for fallback_name in _provider_candidates_for_fallback(primary_name):
        try:
            provider = _get_named_provider(fallback_name)
        except Exception:
            continue

        # Do not select an unconfigured remote provider merely because its
        # section exists. Ollama is intentionally excluded from automatic
        # cloud fallbacks; local inference remains an explicit choice.
        if fallback_name != "ollama" and not _provider_has_credentials(fallback_name):
            continue
        return provider, fallback_name

    return None, None


def _primary_failed(events: list[dict]) -> bool:
    for event in events:
        if event.get("type") == "error" and _is_retryable_provider_error(event):
            return True

        if event.get("type") == "done" and event.get("error"):
            return _is_retryable_provider_error(event)

    return False


def _has_partial_output(events: list[dict]) -> bool:
    """Return True once the primary provider has exposed user-visible text."""
    return any(event.get("type") == "tokens" and bool(str(event.get("content") or "")) for event in events)


def _provider_has_credentials(name: str) -> bool:
    config = get_provider_config(name)
    if name == "ollama":
        return True
    return bool(str(config.get("api_key") or "").strip())


def chat(
    messages: list[dict],
    tools: list[dict] | None = None,
    provider_name: str | None = None,
) -> Generator[dict, None, None]:
    """Stream from a selected provider with safe per-request fallback.

    Normal callers use the configured cloud-first primary provider. Coding
    callers can explicitly select Zen Coder without changing normal chat or
    planning. A missing optional provider falls back to another configured
    remote provider; local Ollama is never an automatic fallback.
    """
    provider = _ensure_provider() if provider_name is None else None
    selected_name = provider_name or _provider_name or "unknown"

    if provider_name is not None:
        if not _provider_has_credentials(provider_name):
            fallback, fallback_name = _get_fallback_provider(provider_name)
            if fallback is None:
                yield {
                    "type": "error",
                    "error": f"Provider '{provider_name}' is not configured",
                    "content": f"Provider '{provider_name}' is not configured",
                    "final": True,
                }
                return
            yield {
                "type": "tokens",
                "content": f"[{provider_name} unavailable; switching to {fallback_name}…]\n\n",
            }
            try:
                yield from fallback.chat(messages, tools=tools)
            except Exception as exc:
                yield {"type": "error", "content": str(exc), "final": True}
            return

        try:
            provider = _get_named_provider(provider_name)
        except Exception as exc:
            fallback, fallback_name = _get_fallback_provider(provider_name)
            if fallback is None:
                yield {"type": "error", "content": str(exc), "final": True}
                return
            yield {
                "type": "tokens",
                "content": f"[{provider_name} unavailable; switching to {fallback_name}…]\n\n",
            }
            try:
                yield from fallback.chat(messages, tools=tools)
            except Exception as fallback_exc:
                yield {"type": "error", "content": str(fallback_exc), "final": True}
            return

    primary_events: list[dict] = []

    try:
        for event in provider.chat(messages, tools=tools):
            if isinstance(event, dict):
                primary_events.append(event)
            yield event
    except Exception as exc:
        primary_events.append({"type": "error", "error": str(exc)})

    if _has_partial_output(primary_events) or not _primary_failed(primary_events):
        return

    fallback, fallback_name = _get_fallback_provider(selected_name)

    if fallback is None:
        return

    yield {
        "type": "tokens",
        "content": (f"[{selected_name} unavailable; switching to {fallback_name}…]\n\n"),
    }

    try:
        yield from fallback.chat(messages, tools=tools)
    except Exception as exc:
        yield {
            "type": "error",
            "content": str(exc),
            "final": True,
        }
