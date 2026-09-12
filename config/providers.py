import os
import tomllib
from typing import Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "providers.toml")


_DEFAULT_CONFIG: dict[str, Any] = {
    "default": {"provider": "openrouter"},
    "routing": {
        "primary": "",
        "fallback": ["openai", "gemini", "deepseek", "zen_coder"],
    },
    "openai": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-5.6-luna",
        "temperature": 0.7,
        "max_tokens": 4096,
        "provider_name": "openai",
    },
    "openrouter": {
        "api_key": "",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/free",
        "fallback_model": "",
        "timeout": 45,
        "temperature": 0.7,
        "max_tokens": 4096,
        "provider_name": "openrouter",
    },
    "gemini": {
        "api_key": "",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3.8-flash",
        "timeout": 45,
        "temperature": 0.7,
        "max_tokens": 4096,
        "provider_name": "gemini",
    },
    "deepseek": {
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "temperature": 0.7,
        "max_tokens": 4096,
        "provider_name": "deepseek",
    },
    "zen_coder": {
        "api_key": "",
        "base_url": "https://opencode.ai/zen/v1",
        "model": "mimo-v2.5-free",
        "fallback_provider": "openrouter",
        "timeout": 60,
        "temperature": 0.2,
        "max_tokens": 8192,
        "provider_name": "zen_coder",
    },
    "embeddings": {"engine": "tfidf"},
}


def _load_dotenv():
    """Load .env file from project root if present."""
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


def load_provider_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {
        key: (value.copy() if isinstance(value, dict) else value)
        for key, value in _DEFAULT_CONFIG.items()
    }

    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "rb") as f:
            user_cfg = tomllib.load(f)
        for section, values in user_cfg.items():
            if isinstance(values, dict) and isinstance(cfg.get(section), dict):
                cfg[section].update(values)
            else:
                cfg[section] = values

    env_map = {
        "openai": ("OPENAI_API_KEY",),
        "openrouter": ("OPENROUTER_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "deepseek": ("DEEPSEEK_API_KEY",),
        "zen_coder": ("ZEN_CODER_API_KEY",),
    }
    for section, env_vars in env_map.items():
        for env_var in env_vars:
            resolved = os.environ.get(env_var, "")
            if resolved:
                cfg[section]["api_key"] = resolved
                break

    return cfg


def _is_configured(config: dict[str, Any], name: str) -> bool:
    provider_cfg = config.get(name, {})
    return bool(isinstance(provider_cfg, dict) and str(provider_cfg.get("api_key") or "").strip())


def get_active_provider(config: dict[str, Any] | None = None) -> str:
    """Select a configured cloud provider; never select a local runtime."""
    if config is None:
        config = load_provider_config()

    default = str(config.get("default", {}).get("provider", "")).strip()
    routing = config.get("routing", {})
    primary = str(routing.get("primary", "")).strip() if isinstance(routing, dict) else ""

    if primary and primary != "local" and _is_configured(config, primary):
        return primary

    if default and default != "local" and _is_configured(config, default):
        return default

    for name in ("openrouter", "openai", "gemini", "deepseek", "zen_coder"):
        if _is_configured(config, name):
            return name

    return "openrouter"


def get_provider_config(name: str | None = None) -> dict[str, Any]:
    config = load_provider_config()
    if name is None:
        name = get_active_provider(config)
    return config.get(name, {})
