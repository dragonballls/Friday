"""Privacy/network restriction mode.

Blackout blocks outbound tools, but Friday remains cloud-provider-only: it never
switches model inference to a local runtime.
"""

import json
import os
import threading

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STORE_PATH = os.path.join(os.path.join(_APP_DIR, "memory_store"), "blackout.json")
_lock = threading.Lock()
_enabled: bool | None = None

_NETWORK_TOOLS = {
    "web_fetch", "browse_search", "browse_get_page_text", "browse_click", "browse_navigate",
    "browse_screenshot", "fetch_news", "fetch_weather", "fetch_stocks", "fetch_crypto",
    "fetch_github_trending", "fetch_cve", "fetch_space", "fetch_earthquakes", "fetch_world_clock",
    "email_send", "calendar_create_event",
}


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
    return {"enabled": is_blackout(), "local_provider": None, "blocked_tools": sorted(_NETWORK_TOOLS)}


def is_tool_blocked(tool: str) -> bool:
    return is_blackout() and tool in _NETWORK_TOOLS


def resolve_provider(requested: str | None) -> str | None:
    """Preserve explicit cloud providers and never force a local model."""
    if requested == "ollama":
        raise ValueError("Friday is cloud-only; local Ollama inference is disabled")
    return requested
