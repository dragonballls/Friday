from __future__ import annotations

from config.providers import get_active_provider, get_provider_config
from providers.openai_compat import OpenAICompatibleProvider
from providers.registry import get_provider_class, register_provider

register_provider("openai", OpenAICompatibleProvider)
register_provider("openrouter", OpenAICompatibleProvider)
register_provider("openai_compatible", OpenAICompatibleProvider)
register_provider("zen_coder", OpenAICompatibleProvider)


def get_provider(name: str | None = None):
    resolved = get_active_provider() if name is None else name
    if resolved == "ollama":
        raise ValueError("Friday is cloud-only; local Ollama inference is disabled")
    cls = get_provider_class(resolved)
    return cls(get_provider_config(resolved))
