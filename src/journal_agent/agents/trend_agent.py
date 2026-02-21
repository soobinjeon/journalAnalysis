"""TrendAgent — generates trend reports for research areas."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Optional

from rich.console import Console

from ..models import TrendReport
from ..storage import Storage
from ..llm.base import BaseLLM


class TrendAgent:
    """Analyzes collected papers to generate trend reports."""

    def __init__(self, storage: Storage, llm: Optional[BaseLLM] = None):
        self.storage = storage
        self.llm = llm
        self.console = Console()

    def generate_report(
        self,
        area_name: str,
        period_days: int = 7,
    ) -> TrendReport | None:
        """Generate a trend report for the given area and period.

        Args:
            area_name: Research area name.
            period_days: Number of days to look back.

        Returns:
            TrendReport or None if no papers found.
        """
        papers = self.storage.get_papers(area=area_name, recent_days=period_days, limit=200)

        if not papers:
            self.console.print(f"[yellow]No papers found for '{area_name}' in the last {period_days} days.[/]")
            return None

        # Collect all keywords from papers and their analyses
        keyword_counter: Counter = Counter()
        top_papers: list[tuple[float, int]] = []  # (score, paper_id)

        for paper in papers:
            # Count keywords from paper
            for kw in paper.keywords:
                keyword_counter[kw.lower()] += 1

            # Also extract from title
            title_words = re.findall(r"[a-z][a-z'-]{2,}", paper.title.lower())
            for w in title_words:
                if len(w) > 3:
                    keyword_counter[w] += 1

            # Get analysis if available
            if paper.id:
                analysis = self.storage.get_analysis(paper.id)
                if analysis:
                    for kw in analysis.extracted_keywords:
                        keyword_counter[kw.lower()] += 1
                    top_papers.append((analysis.importance_score, paper.id))

        # If no analyses yet, rank by citation count
        if not top_papers:
            for paper in papers:
                if paper.id:
                    score = paper.citation_count + (10 if paper.open_access else 0)
                    top_papers.append((float(score), paper.id))

        # Sort by score descending
        top_papers.sort(reverse=True)
        top_paper_ids = [pid for _, pid in top_papers[:10]]

        # Hot keywords (top 15)
        hot_keywords = [kw for kw, _ in keyword_counter.most_common(15)]

        # Generate summary (LLM or rule-based)
        paper_titles = [p.title for p in papers]
        summary = self._generate_summary(
            area_name, papers, hot_keywords, period_days, paper_titles
        )

        period_end = date.today()
        period_start = period_end - timedelta(days=period_days)

        report = TrendReport(
            area_name=area_name,
            period_start=period_start,
            period_end=period_end,
            hot_keywords=hot_keywords,
            top_paper_ids=top_paper_ids,
            summary=summary,
            total_papers=len(papers),
        )

        self.storage.save_trend_report(report)
        self.console.print(f"[bold green]Trend report generated:[/] {len(papers)} papers analyzed.")
        return report

    def _generate_summary(
        self,
        area_name: str,
        papers: list,
        hot_keywords: list[str],
        period_days: int,
        paper_titles: list[str] | None = None,
    ) -> str:
        """Generate a text summary for the trend report."""
        # Try LLM-powered narrative summary
        if self.llm and paper_titles:
            try:
                llm_summary = self.llm.analyze_trends(
                    area_name, paper_titles, hot_keywords
                )
                if llm_summary and not llm_summary.startswith("["):
                    return llm_summary
            except Exception:
                pass

        # Fallback: rule-based summary
        total = len(papers)
        oa_count = sum(1 for p in papers if p.open_access)

        source_counts: Counter = Counter()
        for p in papers:
            source_counts[p.source.value] += 1

        venue_counts: Counter = Counter()
        for p in papers:
            if p.venue:
                venue_counts[p.venue] += 1
        top_venues = venue_counts.most_common(5)

        lines = [
            f"📊 Trend Report: {area_name}",
            f"Period: last {period_days} days | Total papers: {total} | Open Access: {oa_count}",
            "",
            f"🔥 Hot Keywords: {', '.join(hot_keywords[:8])}",
            "",
            "📚 Sources: " + ", ".join(f"{s}: {c}" for s, c in source_counts.most_common()),
        ]

        if top_venues:
            lines.append(
                "🏛️ Top Venues: "
                + ", ".join(f"{v} ({c})" for v, c in top_venues)
            )

        return "\n".join(lines)
