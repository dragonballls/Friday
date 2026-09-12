import os
import tomllib
from typing import Any

from core.credential_store import get_credential, set_credential
from config.free_ai_policy import enforce_free_provider, free_only_enabled

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "providers.toml")


# ─── Env var helpers ─────────────────────────────────────────────
def _load_windows_user_env(key: str) -> str:
    """Read a user-level environment variable directly on Windows."""
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ,
        ) as registry_key:
            value, _ = winreg.QueryValueEx(registry_key, key)
            return str(value).strip()
    except (FileNotFoundError, OSError, TypeError):
        return ""


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


def _resolve_api_key(toml_key: str, env_var: str) -> str:
    """Resolve a key without requiring a shell, then migrate it to secure storage."""
    value = os.environ.get(env_var, "").strip()
    if value:
        try:
            set_credential(env_var, value)
        except OSError:
            pass
        return value

    value = get_credential(env_var).strip()
    if value:
        return value

    value = _load_windows_user_env(env_var)
    if value:
        try:
            set_credential(env_var, value)
        except OSError:
            pass
        return value

    return os.environ.get(toml_key, "").strip()


def load_provider_config() -> dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        cfg: dict[str, Any] = {
            "default": {"provider": "openrouter"},
            "openrouter": {
                "api_key": "",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openrouter/free",
                "fallback_provider": "",
                "timeout": 60,
                "temperature": 0.2,
                "max_tokens": 8192,
                "provider_name": "openrouter",
                "free_only": True,
            },
        }
    else:
        with open(CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)

    # Keep the optional Zen coding provider available even when an older local
    # providers.toml predates this integration. The secret remains external.
    cfg.setdefault(
        "zen_coder",
        {
            "api_key": "",
            "base_url": "https://opencode.ai/zen/v1",
            "model": "mimo-v2.5-free",
            "fallback_provider": "openrouter",
            "timeout": 60,
            "temperature": 0.2,
            "max_tokens": 8192,
            "provider_name": "zen_coder",
        },
    )

    # Provider keys are resolved at runtime. Secrets are never committed to GitHub.
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

    # Free-only mode is mandatory by default. A configured provider that is not
    # explicitly safe for free use is left present for diagnostics but cannot be
    # selected for inference. OpenRouter is pinned to its zero-price router.
    if free_only_enabled():
        for name, provider_cfg in list(cfg.items()):
            if not isinstance(provider_cfg, dict) or name in {"default", "routing"}:
                continue
            try:
                cfg[name] = enforce_free_provider(name, provider_cfg)
            except ValueError:
                provider_cfg["free_only_blocked"] = True

        cfg["default"] = {"provider": "openrouter"}
        cfg["routing"] = {
            **(cfg.get("routing", {}) if isinstance(cfg.get("routing"), dict) else {}),
            "primary": "openrouter",
            "fallback": [],
        }

    return cfg


def get_active_provider(config: dict[str, Any] | None = None) -> str:
    """Return the configured provider, constrained by free-only policy."""
    if config is None:
        config = load_provider_config()

    if free_only_enabled():
        return "openrouter"

    default = str(config.get("default", {}).get("provider", "")).strip()
    routing = config.get("routing", {})
    primary = str(routing.get("primary", "")).strip() if isinstance(routing, dict) else ""

    if default == "ollama":
        if primary and primary != "ollama":
            return primary
        return "openrouter"

    if primary and primary != "ollama" and (not default or default == "ollama"):
        return primary
    return default or primary or "openrouter"


def get_provider_config(name: str | None = None) -> dict[str, Any]:
    config = load_provider_config()
    if name is None:
        name = get_active_provider(config)
    provider_cfg = dict(config.get(name, {}))
    if free_only_enabled():
        provider_cfg = enforce_free_provider(name, provider_cfg)
    return provider_cfg
