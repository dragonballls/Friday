import os
import tomllib
from typing import Any

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "providers.toml")


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
    return os.environ.get(env_var, "") or os.environ.get(toml_key, "")


def load_provider_config() -> dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        cfg: dict[str, Any] = {"default": {"provider": "openrouter"}}
    else:
        with open(CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)

    cfg.setdefault("zen_coder", {
        "api_key": "", "base_url": "https://opencode.ai/zen/v1",
        "model": "mimo-v2.5-free", "fallback_provider": "openrouter",
        "timeout": 60, "temperature": 0.2, "max_tokens": 8192,
        "provider_name": "zen_coder",
    })

    env_map = {
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "zen_coder": "ZEN_CODER_API_KEY",
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "github_models": "GITHUB_TOKEN",
        "nvidia_nim": "NVIDIA_API_KEY",
    }
    for section, env_var in env_map.items():
        if section in cfg:
            resolved = _resolve_api_key("api_key", env_var)
            if resolved:
                cfg[section]["api_key"] = resolved

    cloudflare = cfg.get("cloudflare_workers_ai")
    if isinstance(cloudflare, dict):
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        if token:
            cloudflare["api_key"] = token
        if account_id:
            cloudflare["base_url"] = (
                "https://api.cloudflare.com/client/v4/accounts/" + account_id + "/ai/v1"
            )

    return cfg


def get_active_provider(config: dict[str, Any] | None = None) -> str:
    if config is None:
        config = load_provider_config()
    default = str(config.get("default", {}).get("provider", "")).strip()
    routing = config.get("routing", {})
    primary = str(routing.get("primary", "")).strip() if isinstance(routing, dict) else ""
    if default == "ollama":
        return primary if primary and primary != "ollama" else "openrouter"
    if primary and primary != "ollama" and (not default or default == "ollama"):
        return primary
    return default or primary or "openrouter"


def get_provider_config(name: str | None = None) -> dict[str, Any]:
    config = load_provider_config()
    if name is None:
        name = get_active_provider(config)
    return config.get(name, {})
