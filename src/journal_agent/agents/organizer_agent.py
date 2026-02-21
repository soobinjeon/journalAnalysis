"""OrganizerAgent — classifies papers by research area, deduplicates, and tags."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Optional

from rich.console import Console

from ..models import Paper
from ..storage import Storage
from ..llm.base import BaseLLM


class OrganizerAgent:
    """Organizes papers: area classification, deduplication, keyword tagging."""

    def __init__(self, storage: Storage, llm: Optional[BaseLLM] = None):
        self.storage = storage
        self.llm = llm
        self.console = Console()

    def organize(self, area_name: str | None = None) -> dict:
        """Organize papers: classify, deduplicate, tag.

        Returns:
            Summary dict with counts.
        """
        areas = self.storage.get_areas()
        papers = self.storage.get_papers(area=area_name, limit=500)

        classified = 0
        tagged = 0

        for paper in papers:
            # Classify into matching areas based on keyword matching
            matched_areas = self._classify_paper(paper, areas)
            if matched_areas and set(matched_areas) != set(paper.areas):
                paper.areas = list(set(paper.areas + matched_areas))
                classified += 1

            # Extract and tag keywords from title + abstract
            if not paper.keywords:
                paper.keywords = self._extract_keywords(paper)
                tagged += 1

            # Save updated paper
            self.storage.save_paper(paper)

        summary = {
            "total_processed": len(papers),
            "classified": classified,
            "tagged": tagged,
        }

        self.console.print(
            f"[bold green]Organization complete:[/] "
            f"{len(papers)} papers processed, "
            f"{classified} classified, {tagged} tagged."
        )
        return summary

    def _classify_paper(self, paper: Paper, areas: list) -> list[str]:
        """Classify a paper into research areas — LLM if available, else keyword match."""
        # Try LLM-based classification first
        if self.llm and paper.abstract:
            try:
                area_names = [a.name for a in areas]
                result = self.llm.classify_paper(paper.title, paper.abstract, area_names)
                if result:
                    return result
            except Exception:
                pass

        # Fallback: keyword matching
        text = f"{paper.title} {paper.abstract}".lower()
        matched = []
        for area in areas:
            score = 0
            for kw in area.keywords:
                if kw.lower() in text:
                    score += 1
            if score > 0:
                matched.append(area.name)
        return matched

    def _extract_keywords(self, paper: Paper, top_n: int = 8) -> list[str]:
        """Extract keywords from paper title and abstract using simple TF approach."""
        text = f"{paper.title} {paper.abstract}".lower()

        # Remove common stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "this", "that", "these", "those", "it", "its", "we", "our",
            "they", "their", "which", "what", "where", "when", "how",
            "more", "also", "than", "then", "not", "no", "such", "each",
            "between", "through", "using", "based", "both", "into", "over",
            "show", "shows", "shown", "use", "used", "new", "first",
            "two", "one", "paper", "propose", "proposed", "method", "approach",
            "results", "however", "while", "well", "within", "about",
            "some", "other", "all", "only", "most", "very", "as",
        }

        # Tokenize
        words = re.findall(r"[a-z][a-z'-]{2,}", text)
        words = [w for w in words if w not in stop_words and len(w) > 2]

        # Also extract bigrams
        bigrams = []
        for i in range(len(words) - 1):
            bigrams.append(f"{words[i]} {words[i+1]}")

        # Count frequencies
        counter = Counter(words)
        bigram_counter = Counter(bigrams)

        # Combine: bigrams with count >= 2, plus top unigrams
        keywords = []
        for bg, cnt in bigram_counter.most_common(top_n):
            if cnt >= 2:
                keywords.append(bg)

        for word, cnt in counter.most_common(top_n * 2):
            if len(keywords) >= top_n:
                break
            if word not in " ".join(keywords):
                keywords.append(word)

        return keywords[:top_n]
