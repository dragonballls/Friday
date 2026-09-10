"""Blackout mode (P5) — one-toggle network/privacy restriction.

When enabled:
- outbound web/network tools are blocked
- the frontend can show a privacy seal on the orb
- AI requests without an explicit provider use the local Ollama provider

Explicit provider selections are preserved. This prevents Friday's cloud
coding provider from being silently redirected to a stopped local Ollama
service merely because blackout mode is enabled.

State persists to ``memory_store/blackout.json`` so it survives restarts.
"""

import json
import os
import threading

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STORE_PATH = os.path.join(os.path.join(_APP_DIR, "memory_store"), "blackout.json")

_lock = threading.Lock()
_enabled: bool | None = None

_NETWORK_TOOLS = {
    "web_fetch",
    "browse_search",
    "browse_get_page_text",
    "browse_click",
    "browse_navigate",
    "browse_screenshot",
    "fetch_news",
    "fetch_weather",
    "fetch_stocks",
    "fetch_crypto",
    "fetch_github_trending",
    "fetch_cve",
    "fetch_space",
    "fetch_earthquakes",
    "fetch_world_clock",
    "email_send",
    "calendar_create_event",
}

_LOCAL_PROVIDER = "ollama"


def _load() -> bool:
    if not os.path.exists(_STORE_PATH):
        return False
    try:
        with open(_STORE_PATH, encoding="utf-8") as f:
            return bool(json.load(f).get("enabled", False))
    except Exception:
        return False


def _save(enabled: bool):
    os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump({"enabled": enabled}, f)


def is_blackout() -> bool:
    global _enabled
    with _lock:
        if _enabled is None:
            _enabled = _load()
        return _enabled


def set_blackout(enabled: bool) -> dict:
    global _enabled
    with _lock:
        _enabled = bool(enabled)
        _save(_enabled)
        return {"enabled": _enabled}


def get_blackout_status() -> dict:
    enabled = is_blackout()
    return {
        "enabled": enabled,
        "local_provider": _LOCAL_PROVIDER,
        "blocked_tools": sorted(_NETWORK_TOOLS),
    }


def is_tool_blocked(tool: str) -> bool:
    return is_blackout() and tool in _NETWORK_TOOLS


def resolve_provider(requested: str | None) -> str | None:
    """Resolve provider selection without silently hijacking explicit requests.

    Blackout remains the default local-inference mode when the caller has not
    selected a provider. An explicit provider (for example ``zen_coder``) is
    preserved so autonomous cloud coding cannot accidentally depend on a
    stopped Ollama service.
    """
    if requested is not None:
        return requested
    if is_blackout():
        return _LOCAL_PROVIDER
    return None
