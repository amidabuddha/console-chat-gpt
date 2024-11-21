MODELS_LIST = {
    "anthropic_models": ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-3-opus-latest"],
    "mistral_models": ["mistral-small-latest", "mistral-large-latest"],
    "openai_models": ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4o", "o1-mini", "o1-preview", "test-helpers"],
    "grok_models": ["grok-beta"],
    "gemini_models": ["gemini-1.5-flash", "gemini-1.5-pro"],
}
MODELS_MAX_TOKEN = {
    "gpt-3.5-turbo": "4096",
    "gpt-4o-mini": "16384",
    "gpt-4o": "16384",
    "o1-mini": "65536",
    "o1-preview": "32768",
    "mistral-small-latest": "32000",
    "mistral-large-latest": "128000",
    "claude-3-5-haiku-latest": "8192",
    "claude-3-5-sonnet-latest": "8192",
    "claude-3-opus-latest": "4096",
    "grok-beta": "131072",
    "gemini-1.5-flash": "8192",
    "gemini-1.5-pro": "8192",
    "test-helpers": "1111",
}
