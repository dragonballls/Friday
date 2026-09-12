from config.providers import load_provider_config
from config.settings import (
    LANGUAGE,
    MAX_ITERATIONS,
    MAX_TOKENS,
    MODEL,
    SYSTEM_PROMPT_EN,
    SYSTEM_PROMPT_HI,
    TEMPERATURE,
    get_system_prompt,
)

PROVIDER_CONFIG = load_provider_config()
