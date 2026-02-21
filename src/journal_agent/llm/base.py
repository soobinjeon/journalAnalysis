"""Base interface for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""

    provider: str  # "openai", "ollama", "gemini", "vllm"
    model: str  # e.g., "gpt-4o", "llama3", "gemini-2.0-flash", etc.
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # For vLLM / Ollama custom endpoints
    temperature: float = 0.3
    max_tokens: int = 1024

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LLMConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system/instruction prompt.

        Returns:
            Generated text response.
        """
        ...

    def summarize_paper(self, title: str, abstract: str) -> str:
        """Summarize a paper using the LLM."""
        from .prompts import PAPER_SUMMARY_PROMPT
        prompt = PAPER_SUMMARY_PROMPT.format(title=title, abstract=abstract)
        return self.generate(prompt, system_prompt="You are an expert academic research analyst.")

    def classify_paper(self, title: str, abstract: str, areas: list[str]) -> list[str]:
        """Classify a paper into research areas."""
        from .prompts import PAPER_CLASSIFY_PROMPT
        areas_str = "\n".join(f"- {a}" for a in areas)
        prompt = PAPER_CLASSIFY_PROMPT.format(
            title=title, abstract=abstract, areas=areas_str
        )
        response = self.generate(prompt, system_prompt="You are an expert research paper classifier.")
        # Parse comma-separated area names from response
        matched = []
        for area in areas:
            if area.lower() in response.lower():
                matched.append(area)
        return matched if matched else []

    def analyze_trends(self, area_name: str, paper_titles: list[str], keywords: list[str]) -> str:
        """Generate a trend analysis narrative."""
        from .prompts import TREND_ANALYSIS_PROMPT
        titles_str = "\n".join(f"- {t}" for t in paper_titles[:20])
        keywords_str = ", ".join(keywords[:15])
        prompt = TREND_ANALYSIS_PROMPT.format(
            area=area_name, titles=titles_str, keywords=keywords_str
        )
        return self.generate(prompt, system_prompt="You are an expert research trend analyst.")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.config.model}>"
