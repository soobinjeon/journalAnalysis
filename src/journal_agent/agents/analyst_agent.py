"""AnalystAgent — analyzes papers: summarization, keyword extraction, scoring."""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..models import Paper, AnalysisResult
from ..storage import Storage
from ..llm.base import BaseLLM
from ..llm.prompts import KEYWORD_EXTRACTION_PROMPT

# Top-tier venues for CS (used in venue ranking)
TOP_VENUES = {
    # Conferences
    "neurips", "nips", "icml", "iclr", "aaai", "ijcai",
    "cvpr", "iccv", "eccv",
    "acl", "emnlp", "naacl",
    "sigir", "www", "kdd",
    "icse", "fse", "ase",
    "osdi", "sosp", "nsdi",
    "sigcomm", "mobicom",
    "stoc", "focs", "soda",
    "chi", "uist", "cscw",
    "usenix security", "s&p", "ccs",
    # Journals
    "nature", "science", "cell",
    "ieee transactions", "ieee tpami", "tpami",
    "acm computing surveys", "jmlr",
    "artificial intelligence", "machine learning",
    "plos one", "pnas",
}


class AnalystAgent:
    """Analyzes papers — extractive summary, keyword extraction, importance scoring.

    When an LLM is provided, uses it for higher-quality summarization and
    keyword extraction. Falls back to TF-IDF / extractive methods otherwise.
    """

    def __init__(self, storage: Storage, llm: Optional[BaseLLM] = None):
        self.storage = storage
        self.llm = llm
        self.console = Console()

    def analyze_papers(self, area_name: str | None = None, limit: int = 50) -> list[AnalysisResult]:
        """Analyze unanalyzed papers. Returns list of new AnalysisResults."""
        papers = self.storage.get_unanalyzed_papers(limit=limit)
        if area_name:
            papers = [p for p in papers if area_name in p.areas]

        if not papers:
            self.console.print("[yellow]No unanalyzed papers found.[/]")
            return []

        mode_label = "[bold magenta]LLM[/]" if self.llm else "[dim]rule-based[/]"
        self.console.print(f"Analysis mode: {mode_label}")

        results: list[AnalysisResult] = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Analyzing {len(papers)} papers...",
                total=len(papers),
            )
            for paper in papers:
                result = self._analyze_single(paper)
                self.storage.save_analysis(result)
                results.append(result)
                progress.advance(task)

        self.console.print(
            f"[bold green]Analysis complete:[/] {len(results)} papers analyzed."
        )
        return results

    def _analyze_single(self, paper: Paper) -> AnalysisResult:
        """Analyze a single paper."""
        summary = self._summarize(paper)
        keywords = self._get_keywords(paper)
        score = self._compute_importance(paper)

        return AnalysisResult(
            paper_id=paper.id,
            summary=summary,
            extracted_keywords=keywords,
            importance_score=score,
        )

    # ── Summarization ───────────────────────────────────────────────

    def _summarize(self, paper: Paper) -> str:
        """Summarize a paper — LLM if available, else extractive."""
        if self.llm and paper.abstract:
            try:
                result = self.llm.summarize_paper(paper.title, paper.abstract)
                if result and not result.startswith("["):  # Skip error messages
                    return result
            except Exception:
                pass  # Fall through to extractive
        return self._extractive_summary(paper.abstract)

    def _extractive_summary(self, abstract: str, max_sentences: int = 3) -> str:
        """Extract top sentences from abstract as summary."""
        if not abstract:
            return "No abstract available."

        sentences = re.split(r"(?<=[.!?])\s+", abstract)
        if len(sentences) <= max_sentences:
            return abstract

        words = set(re.findall(r"\w+", abstract.lower()))
        scored = []
        for i, sent in enumerate(sentences):
            sent_words = set(re.findall(r"\w+", sent.lower()))
            overlap = len(sent_words & words) / max(len(sent_words), 1)
            position_bonus = 0.3 if i == 0 else (0.1 if i == len(sentences) - 1 else 0)
            scored.append((overlap + position_bonus, i, sent))

        scored.sort(reverse=True)
        top = sorted(scored[:max_sentences], key=lambda x: x[1])
        return " ".join(s[2] for s in top)

    # ── Keywords ────────────────────────────────────────────────────

    def _get_keywords(self, paper: Paper) -> list[str]:
        """Extract keywords — LLM if available, else TF."""
        if self.llm and paper.abstract:
            try:
                prompt = KEYWORD_EXTRACTION_PROMPT.format(
                    title=paper.title, abstract=paper.abstract
                )
                result = self.llm.generate(prompt)
                if result and not result.startswith("["):
                    keywords = [k.strip() for k in result.split(",") if k.strip()]
                    if keywords:
                        return keywords[:10]
            except Exception:
                pass
        return self._extract_keywords_tf(paper)

    def _extract_keywords_tf(self, paper: Paper, top_n: int = 10) -> list[str]:
        """Extract keywords from title + abstract using TF."""
        text = f"{paper.title} {paper.abstract}".lower()
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "can",
            "this", "that", "these", "those", "it", "its", "we", "our",
            "they", "their", "which", "what", "where", "when", "how",
            "more", "also", "than", "then", "not", "no", "if",
        }

        words = re.findall(r"[a-z][a-z'-]{2,}", text)
        words = [w for w in words if w not in stop_words]
        counter = Counter(words)
        return [w for w, _ in counter.most_common(top_n)]

    # ── Importance Score ────────────────────────────────────────────

    def _compute_importance(self, paper: Paper) -> float:
        """Compute importance score (0-100) based on citations, venue, and recency."""
        citation_score = min(paper.citation_count / 100, 1.0) * 40

        venue_score = 0
        if paper.venue:
            venue_lower = paper.venue.lower()
            for tv in TOP_VENUES:
                if tv in venue_lower:
                    venue_score = 30
                    break
            if venue_score == 0 and paper.venue:
                venue_score = 10

        recency_score = 0
        if paper.published_date:
            from datetime import date
            days_ago = (date.today() - paper.published_date).days
            if days_ago <= 7:
                recency_score = 30
            elif days_ago <= 30:
                recency_score = 25
            elif days_ago <= 90:
                recency_score = 15
            elif days_ago <= 365:
                recency_score = 5

        return round(citation_score + venue_score + recency_score, 1)
