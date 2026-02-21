"""CollectorAgent — orchestrates paper collection from all sources."""

from __future__ import annotations

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..collectors.arxiv import ArxivCollector
from ..collectors.semantic_scholar import SemanticScholarCollector
from ..collectors.crossref import CrossRefCollector
from ..collectors.dblp import DBLPCollector
from ..models import Paper
from ..storage import Storage


class CollectorAgent:
    """Collects papers from all sources for given keywords, deduplicates, and stores."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self.collectors = [
            ArxivCollector(),
            SemanticScholarCollector(),
            CrossRefCollector(),
            DBLPCollector(),
        ]
        self.console = Console()

    def collect(
        self,
        keywords: list[str],
        area_name: str | None = None,
        max_per_source: int = 15,
    ) -> list[Paper]:
        """Collect papers from all sources for the given keywords.

        Args:
            keywords: List of search keywords/phrases.
            area_name: Optional research area name to tag papers with.
            max_per_source: Max results per source per keyword.

        Returns:
            List of all collected (deduplicated) papers.
        """
        all_papers: list[Paper] = []
        seen_keys: set[str] = set()

        query = " ".join(keywords)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            for collector in self.collectors:
                task = progress.add_task(
                    f"[cyan]Collecting from {collector.source_name}...",
                    total=None,
                )
                try:
                    papers = collector.search(query, max_results=max_per_source)
                    for p in papers:
                        key = p.unique_key
                        if key not in seen_keys:
                            seen_keys.add(key)
                            if area_name:
                                p.areas = [area_name]
                            all_papers.append(p)
                    progress.update(
                        task,
                        description=f"[green]✓ {collector.source_name}: {len(papers)} papers",
                    )
                except Exception as e:
                    progress.update(
                        task,
                        description=f"[red]✗ {collector.source_name}: {e}",
                    )

        # Save to storage
        new_count = self.storage.save_papers(all_papers)
        self.console.print(
            f"\n[bold green]Collection complete:[/] "
            f"{len(all_papers)} papers found, {new_count} new papers saved."
        )
        return all_papers
