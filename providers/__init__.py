from __future__ import annotations

from config.providers import get_active_provider, get_provider_config
from providers.openai_compat import OpenAICompatibleProvider
from providers.registry import get_provider_class, register_provider

for _name in (
    "openai",
    "openrouter",
    "openai_compatible",
    "zen_coder",
    "groq",
    "gemini",
    "cerebras",
    "mistral",
    "github_models",
    "cloudflare_workers_ai",
    "nvidia_nim",
):
    register_provider(_name, OpenAICompatibleProvider)


def get_provider(name: str | None = None):
    resolved = get_active_provider() if name is None else name
    if resolved == "ollama":
        raise ValueError("Friday is cloud-only; local Ollama inference is disabled")
    cls = get_provider_class(resolved)
    return cls(get_provider_config(resolved))
