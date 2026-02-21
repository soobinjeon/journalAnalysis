"""vLLM provider for on-premise deployment (OpenAI-compatible API)."""

from __future__ import annotations

from typing import Optional

import httpx

from .base import BaseLLM, LLMConfig


class VllmLLM(BaseLLM):
    """LLM provider using a vLLM server (OpenAI-compatible API).

    vLLM serves models via an OpenAI-compatible REST API,
    so this provider uses the same chat/completions endpoint format.
    The key difference is the base_url points to the vLLM server.

    Example:
        config = LLMConfig(
            provider="vllm",
            model="meta-llama/Llama-3-8b-chat-hf",
            base_url="http://your-gpu-server:8000/v1",
        )
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not config.base_url:
            raise ValueError(
                "vLLM requires base_url pointing to your vLLM server. "
                "Example: http://your-gpu-server:8000/v1"
            )
        self.base_url = config.base_url.rstrip("/")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
                timeout=120,  # On-premise can be slow depending on hardware
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.ConnectError:
            return f"[vLLM Error] Cannot connect to vLLM server at {self.base_url}"
        except httpx.HTTPError as e:
            return f"[vLLM Error] {e}"
        except (KeyError, IndexError) as e:
            return f"[vLLM Parse Error] {e}"
