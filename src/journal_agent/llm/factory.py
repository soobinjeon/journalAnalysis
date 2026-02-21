"""LLM provider factory and configuration management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .base import BaseLLM, LLMConfig

CONFIG_PATH = Path.home() / ".journal_agent" / "llm_config.json"


def create_llm(config: LLMConfig) -> BaseLLM:
    """Factory function to create an LLM provider from config.

    Args:
        config: LLMConfig with provider, model, etc.

    Returns:
        An instance of the appropriate LLM provider.

    Raises:
        ValueError: If the provider is unknown.
    """
    provider = config.provider.lower()

    if provider == "openai":
        from .openai_llm import OpenAILLM
        # Auto-fill API key from env if not set
        if not config.api_key:
            config.api_key = os.environ.get("OPENAI_API_KEY")
        return OpenAILLM(config)

    elif provider == "ollama":
        from .ollama_llm import OllamaLLM
        return OllamaLLM(config)

    elif provider == "gemini":
        from .gemini_llm import GeminiLLM
        if not config.api_key:
            config.api_key = os.environ.get("GEMINI_API_KEY")
        return GeminiLLM(config)

    elif provider == "vllm":
        from .vllm_llm import VllmLLM
        return VllmLLM(config)

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            f"Supported: openai, ollama, gemini, vllm"
        )


def save_llm_config(config: LLMConfig) -> None:
    """Save LLM config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = config.to_dict()
    # Never save API keys to disk — use env vars
    data.pop("api_key", None)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def load_llm_config() -> Optional[LLMConfig]:
    """Load LLM config from disk, if it exists."""
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text())
        return LLMConfig.from_dict(data)
    except (json.JSONDecodeError, TypeError):
        return None


def get_llm() -> Optional[BaseLLM]:
    """Get the configured LLM provider, or None if not configured."""
    config = load_llm_config()
    if config is None:
        return None
    try:
        return create_llm(config)
    except ValueError:
        return None
