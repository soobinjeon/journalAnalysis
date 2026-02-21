"""Ollama LLM provider (local models: Llama3, Mistral, etc.)."""

from __future__ import annotations

from typing import Optional

import httpx

from .base import BaseLLM, LLMConfig


class OllamaLLM(BaseLLM):
    """LLM provider using a local Ollama instance."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Use the /api/chat endpoint for conversation-style interaction
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                    },
                },
                timeout=120,  # Local models can be slow
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        except httpx.ConnectError:
            return "[Ollama Error] Cannot connect to Ollama. Is it running? (ollama serve)"
        except httpx.HTTPError as e:
            return f"[Ollama Error] {e}"
        except (KeyError, IndexError) as e:
            return f"[Ollama Parse Error] {e}"
