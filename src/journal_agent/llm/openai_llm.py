"""OpenAI LLM provider (GPT-4o, GPT-4o-mini, etc.)."""

from __future__ import annotations

from typing import Optional

import httpx

from .base import BaseLLM, LLMConfig


class OpenAILLM(BaseLLM):
    """LLM provider using the OpenAI API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not config.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY or pass api_key.")
        self.base_url = config.base_url or "https://api.openai.com/v1"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPError as e:
            return f"[OpenAI Error] {e}"
        except (KeyError, IndexError) as e:
            return f"[OpenAI Parse Error] {e}"
