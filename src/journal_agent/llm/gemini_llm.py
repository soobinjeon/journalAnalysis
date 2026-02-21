"""Google Gemini LLM provider."""

from __future__ import annotations

from typing import Optional

import httpx

from .base import BaseLLM, LLMConfig


class GeminiLLM(BaseLLM):
    """LLM provider using the Google Gemini API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not config.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY or pass api_key.")
        self.base_url = config.base_url or "https://generativelanguage.googleapis.com/v1beta"

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        url = f"{self.base_url}/models/{self.config.model}:generateContent"

        # Build contents
        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": system_prompt}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow these instructions."}],
            })
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}],
        })

        try:
            resp = httpx.post(
                url,
                params={"key": self.config.api_key},
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": self.config.temperature,
                        "maxOutputTokens": self.config.max_tokens,
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract text from response
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()

            return "[Gemini] No response generated."
        except httpx.HTTPError as e:
            return f"[Gemini Error] {e}"
        except (KeyError, IndexError) as e:
            return f"[Gemini Parse Error] {e}"
