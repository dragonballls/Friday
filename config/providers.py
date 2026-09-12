import os
import tomllib
from typing import Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "providers.toml")


def _load_windows_user_env(key: str) -> str:
    """Read a user-level environment variable directly on Windows."""
    if os.name != "nt":
        return ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ) as registry_key:
            value, _ = winreg.QueryValueEx(registry_key, key)
            return str(value).strip()
    except (FileNotFoundError, OSError, TypeError):
        return ""


def _load_dotenv():
    root = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(root, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            if not os.environ.get(key):
                os.environ[key] = val


_load_dotenv()


def _resolve_api_key(toml_key: str, env_var: str) -> str:
    return os.environ.get(env_var, "") or _load_windows_user_env(env_var) or os.environ.get(toml_key, "")


def load_provider_config() -> dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        cfg: dict[str, Any] = {"default": {"provider": "openrouter"}}
    else:
        with open(CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)

    cfg.setdefault("zen_coder", {
        "api_key": "",
        "base_url": "https://opencode.ai/zen/v1",
        "model": "mimo-v2.5-free",
        "fallback_provider": "openrouter",
        "timeout": 60,
        "temperature": 0.2,
        "max_tokens": 8192,
        "provider_name": "zen_coder",
    })

    env_map = {
        "openai": ("api_key", "OPENAI_API_KEY"),
        "openrouter": ("api_key", "OPENROUTER_API_KEY"),
        "zen_coder": ("api_key", "ZEN_CODER_API_KEY"),
    }
    for section, (field, env_var) in env_map.items():
        if section in cfg:
            resolved = _resolve_api_key(field, env_var)
            if resolved:
                cfg[section][field] = resolved

    return cfg


def get_active_provider(config: dict[str, Any] | None = None) -> str:
    """Select a configured cloud provider without producing false credential errors.

    An explicit remote default stays authoritative when it has a key. If that
    default lacks a credential, another supported cloud provider with a credential
    is selected instead so packaged builds can use the user's configured cloud key.
    """
    if config is None:
        config = load_provider_config()

    default = str(config.get("default", {}).get("provider", "")).strip()
    routing = config.get("routing", {})
    primary = str(routing.get("primary", "")).strip() if isinstance(routing, dict) else ""

    openrouter_key = str(config.get("openrouter", {}).get("api_key", "")).strip()
    openai_key = str(config.get("openai", {}).get("api_key", "")).strip()
    cloud_keys = {"openrouter": bool(openrouter_key), "openai": bool(openai_key)}

    if default in cloud_keys:
        if cloud_keys[default]:
            return default
        for provider in ("openrouter", "openai"):
            if cloud_keys[provider]:
                return provider
        return default

    if default == "ollama":
        if primary and primary != "ollama":
            return primary
        for provider in ("openrouter", "openai"):
            if cloud_keys[provider]:
                return provider
        return "openrouter"

    if primary and primary != "ollama":
        return primary
    for provider in ("openrouter", "openai"):
        if cloud_keys[provider]:
            return provider
    return default or "openrouter"


def get_provider_config(name: str | None = None) -> dict[str, Any]:
    config = load_provider_config()
    if name is None:
        name = get_active_provider(config)
    return config.get(name, {})
