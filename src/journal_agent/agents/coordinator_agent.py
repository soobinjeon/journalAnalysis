"""CoordinatorAgent — orchestrates the full pipeline from CLI commands."""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from ..storage import Storage
from ..llm.base import BaseLLM
from ..llm.factory import get_llm
from .collector_agent import CollectorAgent
from .organizer_agent import OrganizerAgent
from .analyst_agent import AnalystAgent
from .trend_agent import TrendAgent


class CoordinatorAgent:
    """Top-level agent that coordinates the entire pipeline.

    Automatically loads LLM config if available and passes it to sub-agents.
    """

    def __init__(self, storage: Storage | None = None, llm: Optional[BaseLLM] = None):
        self.storage = storage or Storage()

        # Auto-load LLM if not explicitly provided
        if llm is None:
            llm = get_llm()

        self.llm = llm
        self.collector = CollectorAgent(self.storage)
        self.organizer = OrganizerAgent(self.storage, llm=llm)
        self.analyst = AnalystAgent(self.storage, llm=llm)
        self.trend = TrendAgent(self.storage, llm=llm)
        self.console = Console()

        if llm:
            self.console.print(f"[bold magenta]🤖 LLM enabled:[/] {llm}")

    def run_full_pipeline(self, area_name: str | None = None) -> dict:
        """Run the full collect → organize → analyze → trend pipeline.

        Args:
            area_name: Specific area to process, or None for all areas.

        Returns:
            Summary dict of the pipeline run.
        """
        areas = self.storage.get_areas()
        if area_name:
            areas = [a for a in areas if a.name == area_name]

        if not areas:
            self.console.print("[red]No research areas configured. Add one first.[/]")
            return {"error": "No areas configured"}

        results = {"areas_processed": [], "total_papers": 0, "total_analyzed": 0}

        for area in areas:
            self.console.rule(f"[bold blue]📥 Collecting: {area.name}")

            # 1. Collect
            papers = self.collector.collect(
                keywords=area.keywords,
                area_name=area.name,
            )
            results["total_papers"] += len(papers)

            # 2. Organize
            self.console.rule(f"[bold blue]📂 Organizing: {area.name}")
            self.organizer.organize(area_name=area.name)

            # 3. Analyze
            self.console.rule(f"[bold blue]🔬 Analyzing: {area.name}")
            analysis_results = self.analyst.analyze_papers(area_name=area.name)
            results["total_analyzed"] += len(analysis_results)

            # 4. Trend
            self.console.rule(f"[bold blue]📊 Trend Report: {area.name}")
            self.trend.generate_report(area_name=area.name)

            results["areas_processed"].append(area.name)

        self.console.print()
        self.console.rule("[bold green]✅ Pipeline Complete")
        return results

    def collect_only(self, area_name: str | None = None) -> list:
        """Run collection only."""
        areas = self.storage.get_areas()
        if area_name:
            areas = [a for a in areas if a.name == area_name]

        all_papers = []
        for area in areas:
            self.console.rule(f"[bold blue]📥 Collecting: {area.name}")
            papers = self.collector.collect(
                keywords=area.keywords,
                area_name=area.name,
            )
            all_papers.extend(papers)

            # Also organize after collection
            self.organizer.organize(area_name=area.name)

        return all_papers

    def analyze_only(self, area_name: str | None = None) -> list:
        """Run analysis only on existing papers."""
        return self.analyst.analyze_papers(area_name=area_name)

    def trends_only(self, area_name: str, period_days: int = 7):
        """Generate trend report only."""
        return self.trend.generate_report(area_name, period_days)
