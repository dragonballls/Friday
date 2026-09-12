from collections.abc import Generator

from providers import get_provider
from config.providers import get_provider_config, load_provider_config

_provider = None
_provider_name = None
_provider_cache: dict[str, object] = {}
_LOCAL_PROVIDERS = {"ollama"}


def _ensure_provider():
    global _provider, _provider_name
    if _provider is None:
        _provider = get_provider()
        _provider_name = getattr(_provider, "name", None) or "unknown"
    return _provider


def _get_named_provider(name: str):
    if name in _LOCAL_PROVIDERS:
        raise ValueError("Friday is cloud-only; local AI providers are disabled")
    provider = _provider_cache.get(name)
    if provider is None:
        provider = get_provider(name)
        _provider_cache[name] = provider
    return provider


def _is_retryable_provider_error(event: dict) -> bool:
    text = str(event.get("error") or event.get("content") or "").lower()
    return any(marker in text for marker in ("429", "rate limit", "rate_limit", "free-models-per-day", "timeout", "timed out", "connection", "connecterror", "connectionerror", "temporarily unavailable", "service unavailable", "502", "503", "504"))


def _provider_candidates_for_fallback(primary_name: str) -> list[str]:
    config = load_provider_config()
    primary_config = config.get(primary_name, {})
    configured = str(primary_config.get("fallback_provider", "")).strip()
    candidates: list[str] = []
    if configured and configured != primary_name and configured not in _LOCAL_PROVIDERS:
        candidates.append(configured)
    routing = config.get("routing", {})
    if isinstance(routing, dict):
        fallback_list = routing.get("fallback", [])
        if isinstance(fallback_list, str):
            fallback_list = [fallback_list]
        if isinstance(fallback_list, list):
            candidates.extend(str(item).strip() for item in fallback_list if str(item).strip() not in _LOCAL_PROVIDERS)
    seen: set[str] = set()
    return [name for name in candidates if name and name != primary_name and not (name in seen or seen.add(name))]


def _get_fallback_provider(primary_name: str, *, allow_uncredentialed: bool = False):
    for fallback_name in _provider_candidates_for_fallback(primary_name):
        try:
            cached = _provider_cache.get(fallback_name)
            provider = cached if cached is not None else _get_named_provider(fallback_name)
        except Exception:
            continue
        if not allow_uncredentialed and not _provider_has_credentials(fallback_name):
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


def chat(messages: list[dict], tools: list[dict] | None = None, provider_name: str | None = None) -> Generator[dict, None, None]:
    provider = _ensure_provider() if provider_name is None else None
    selected_name = provider_name or _provider_name or "unknown"
    if selected_name in _LOCAL_PROVIDERS:
        yield {"type": "error", "error": "Friday is cloud-only; local AI providers are disabled", "content": "Friday is cloud-only; local AI providers are disabled", "final": True}
        return

    if provider_name is not None:
        if not _provider_has_credentials(provider_name):
            fallback, fallback_name = _get_fallback_provider(provider_name)
            if fallback is None:
                yield {"type": "error", "error": f"Provider '{provider_name}' is not configured", "content": f"Provider '{provider_name}' is not configured", "final": True}
                return
            yield {"type": "tokens", "content": f"[{provider_name} unavailable; switching to {fallback_name}…]\n\n"}
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
            yield {"type": "tokens", "content": f"[{provider_name} unavailable; switching to {fallback_name}…]\n\n"}
            try:
                yield from fallback.chat(messages, tools=tools)
            except Exception as fallback_exc:
                yield {"type": "error", "content": str(fallback_exc), "final": True}
            return

    primary_events: list[dict] = []
    partial_output = False
    try:
        for event in provider.chat(messages, tools=tools):
            if isinstance(event, dict):
                if event.get("type") == "tokens" and bool(str(event.get("content") or "")):
                    partial_output = True
                primary_events.append(event)
                if partial_output and event.get("type") == "error":
                    continue
            yield event
    except Exception as exc:
        error_event = {"type": "error", "error": str(exc), "content": str(exc), "final": True}
        primary_events.append(error_event)
        if not partial_output:
            yield error_event
    if partial_output or not _primary_failed(primary_events):
        return
    fallback, fallback_name = _get_fallback_provider(selected_name)
    if fallback is None:
        return
    yield {"type": "tokens", "content": f"[{selected_name} unavailable; switching to {fallback_name}…]\n\n"}
    try:
        yield from fallback.chat(messages, tools=tools)
    except Exception as exc:
        yield {"type": "error", "content": str(exc), "final": True}


def _provider_has_credentials(name: str) -> bool:
    if name in _LOCAL_PROVIDERS:
        return False
    config = get_provider_config(name)
    return bool(str(config.get("api_key") or "").strip())
