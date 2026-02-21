"""CLI interface for the journal agent system."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from datetime import date

from .models import ResearchArea
from .storage import Storage
from .agents.coordinator_agent import CoordinatorAgent
from .llm.base import LLMConfig
from .llm.factory import save_llm_config, load_llm_config, create_llm

console = Console()


def get_coordinator() -> CoordinatorAgent:
    return CoordinatorAgent()


# ── Main Group ──────────────────────────────────────────────────────

@click.group()
@click.version_option(version="0.1.0", prog_name="journal-agent")
def cli():
    """📚 Journal Agent — Research paper collection, organization & analysis."""
    pass


# ── Areas Commands ──────────────────────────────────────────────────

@cli.group()
def areas():
    """Manage research areas of interest."""
    pass


@areas.command("add")
@click.argument("name")
@click.option("--keywords", "-k", required=True, help="Comma-separated keywords")
def areas_add(name: str, keywords: str):
    """Add a new research area."""
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not kw_list:
        console.print("[red]At least one keyword is required.[/]")
        return

    storage = Storage()
    existing = storage.get_area_by_name(name)
    if existing:
        console.print(f"[yellow]Area '{name}' already exists.[/]")
        return

    area = ResearchArea(name=name, keywords=kw_list)
    storage.add_area(area)
    console.print(f"[green]✓ Added area:[/] [bold]{name}[/]")
    console.print(f"  Keywords: {', '.join(kw_list)}")
    storage.close()


@areas.command("list")
def areas_list():
    """List all research areas."""
    storage = Storage()
    area_list = storage.get_areas()
    storage.close()

    if not area_list:
        console.print("[yellow]No research areas configured. Use 'journal areas add' to add one.[/]")
        return

    table = Table(title="📋 Research Areas", show_lines=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Name", style="bold cyan")
    table.add_column("Keywords", style="green")
    table.add_column("Created", style="dim")

    for area in area_list:
        table.add_row(
            str(area.id),
            area.name,
            ", ".join(area.keywords),
            area.created_at.strftime("%Y-%m-%d") if area.created_at else "-",
        )

    console.print(table)


@areas.command("remove")
@click.argument("name")
def areas_remove(name: str):
    """Remove a research area."""
    storage = Storage()
    if storage.delete_area(name):
        console.print(f"[green]✓ Removed area: {name}[/]")
    else:
        console.print(f"[red]Area '{name}' not found.[/]")
    storage.close()


# ── Collect Command ─────────────────────────────────────────────────

@cli.command()
@click.option("--area", "-a", default=None, help="Specific area to collect for")
@click.option("--max-results", "-n", default=15, help="Max results per source")
def collect(area: str | None, max_results: int):
    """📥 Collect papers from all sources."""
    coord = get_coordinator()

    if area:
        area_obj = coord.storage.get_area_by_name(area)
        if not area_obj:
            console.print(f"[red]Area '{area}' not found. Use 'journal areas list' to see available areas.[/]")
            return

    coord.collect_only(area_name=area)
    coord.storage.close()


# ── Papers Commands ─────────────────────────────────────────────────

@cli.command("papers")
@click.option("--area", "-a", default=None, help="Filter by area")
@click.option("--recent", "-r", default=None, type=int, help="Show papers from last N days")
@click.option("--limit", "-l", default=20, help="Max number of papers to show")
def papers_list(area: str | None, recent: int | None, limit: int):
    """📄 List collected papers."""
    storage = Storage()
    papers = storage.get_papers(area=area, recent_days=recent, limit=limit)
    storage.close()

    if not papers:
        console.print("[yellow]No papers found. Run 'journal collect' first.[/]")
        return

    table = Table(title=f"📄 Papers ({len(papers)} shown)", show_lines=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Title", style="bold", max_width=60)
    table.add_column("Source", style="cyan", width=8)
    table.add_column("Venue", style="green", max_width=20)
    table.add_column("Date", style="dim", width=10)
    table.add_column("OA", width=3)
    table.add_column("Cites", width=5, justify="right")

    for p in papers:
        oa_mark = "✅" if p.open_access else "❌"
        pub_date = p.published_date.isoformat() if p.published_date else "-"
        table.add_row(
            str(p.id),
            p.title[:60],
            p.source.value[:8],
            (p.venue or "-")[:20],
            pub_date,
            oa_mark,
            str(p.citation_count),
        )

    console.print(table)


# ── Paper Detail Command ───────────────────────────────────────────

@cli.command("paper")
@click.argument("paper_id", type=int)
def paper_detail(paper_id: int):
    """🔍 View detailed information about a specific paper."""
    storage = Storage()
    paper = storage.get_paper_by_id(paper_id)

    if not paper:
        console.print(f"[red]Paper #{paper_id} not found.[/]")
        storage.close()
        return

    # Paper info panel
    info_lines = [
        f"[bold cyan]Title:[/] {paper.title}",
        f"[bold cyan]Authors:[/] {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}",
        f"[bold cyan]Source:[/] {paper.source.value}",
        f"[bold cyan]Venue:[/] {paper.venue or 'N/A'}",
        f"[bold cyan]Published:[/] {paper.published_date or 'N/A'}",
        f"[bold cyan]DOI:[/] {paper.doi or 'N/A'}",
        f"[bold cyan]URL:[/] {paper.url}",
        f"[bold cyan]Open Access:[/] {'✅ Yes' if paper.open_access else '❌ No'}",
        f"[bold cyan]Citations:[/] {paper.citation_count}",
        f"[bold cyan]Areas:[/] {', '.join(paper.areas) if paper.areas else 'N/A'}",
        f"[bold cyan]Keywords:[/] {', '.join(paper.keywords) if paper.keywords else 'N/A'}",
    ]
    if paper.pdf_url:
        info_lines.append(f"[bold cyan]PDF:[/] {paper.pdf_url}")

    console.print(Panel("\n".join(info_lines), title=f"📄 Paper #{paper_id}", border_style="blue"))

    # Abstract
    if paper.abstract:
        console.print(Panel(paper.abstract, title="📝 Abstract", border_style="green"))

    # Analysis result
    analysis = storage.get_analysis(paper_id)
    if analysis:
        analysis_lines = [
            f"[bold yellow]Importance Score:[/] {analysis.importance_score}/100",
            f"[bold yellow]Keywords:[/] {', '.join(analysis.extracted_keywords)}",
            "",
            f"[bold yellow]Summary:[/]",
            analysis.summary,
        ]
        console.print(Panel("\n".join(analysis_lines), title="🔬 Analysis", border_style="yellow"))
    else:
        console.print("[dim]Analysis not yet available. Run 'journal analyze' first.[/]")

    storage.close()


# ── Analyze Command ─────────────────────────────────────────────────

@cli.command()
@click.option("--area", "-a", default=None, help="Specific area to analyze")
def analyze(area: str | None):
    """🔬 Analyze collected papers (summarize, score, extract keywords)."""
    coord = get_coordinator()
    coord.analyze_only(area_name=area)
    coord.storage.close()


# ── Trends Command ──────────────────────────────────────────────────

@cli.command()
@click.option("--area", "-a", required=True, help="Area to generate trend report for")
@click.option("--period", "-p", default=7, help="Period in days (default: 7)")
def trends(area: str, period: int):
    """📊 Generate trend report for a research area."""
    coord = get_coordinator()
    report = coord.trends_only(area_name=area, period_days=period)

    if report:
        console.print()

        # Summary panel
        console.print(Panel(
            report.summary,
            title=f"📊 Trend Report: {area}",
            subtitle=f"{report.period_start} → {report.period_end}",
            border_style="magenta",
        ))

        # Hot keywords
        if report.hot_keywords:
            kw_text = " | ".join(f"[bold magenta]{kw}[/]" for kw in report.hot_keywords[:10])
            console.print(f"\n🔥 [bold]Hot Keywords:[/] {kw_text}")

        # Top papers
        if report.top_paper_ids:
            console.print(f"\n📌 [bold]Top Papers:[/]")
            for pid in report.top_paper_ids[:5]:
                paper = coord.storage.get_paper_by_id(pid)
                if paper:
                    analysis = coord.storage.get_analysis(pid)
                    score = f" [yellow](score: {analysis.importance_score})[/]" if analysis else ""
                    console.print(f"  [{pid}] {paper.title[:80]}{score}")

    coord.storage.close()


# ── Pipeline Command ────────────────────────────────────────────────

@cli.command()
@click.option("--area", "-a", default=None, help="Specific area to process")
def pipeline(area: str | None):
    """🚀 Run full pipeline: collect → organize → analyze → trends."""
    coord = get_coordinator()
    coord.run_full_pipeline(area_name=area)
    coord.storage.close()


# ── Status Command ──────────────────────────────────────────────────

@cli.command()
def status():
    """📈 Show system status and statistics."""
    storage = Storage()
    stats = storage.get_stats()
    areas = storage.get_areas()
    storage.close()

    console.print(Panel(
        "\n".join([
            f"[bold cyan]Total Papers:[/]    {stats['total_papers']}",
            f"[bold cyan]Research Areas:[/]  {stats['total_areas']}",
            f"[bold cyan]Analyzed:[/]        {stats['total_analyzed']}",
            f"[bold cyan]Trend Reports:[/]   {stats['total_reports']}",
        ]),
        title="📈 System Status",
        border_style="blue",
    ))

    if stats["papers_by_source"]:
        table = Table(title="Papers by Source")
        table.add_column("Source", style="cyan")
        table.add_column("Count", justify="right")
        for source, count in stats["papers_by_source"].items():
            table.add_row(source, str(count))
        console.print(table)

    if areas:
        table = Table(title="Research Areas")
        table.add_column("Name", style="bold")
        table.add_column("Keywords", style="green")
        for area in areas:
            table.add_row(area.name, ", ".join(area.keywords[:5]))
        console.print(table)

    # LLM config status
    llm_config = load_llm_config()
    if llm_config:
        console.print(Panel(
            "\n".join([
                f"[bold magenta]Provider:[/]    {llm_config.provider}",
                f"[bold magenta]Model:[/]       {llm_config.model}",
                f"[bold magenta]Base URL:[/]    {llm_config.base_url or 'default'}",
                f"[bold magenta]Temperature:[/] {llm_config.temperature}",
            ]),
            title="🤖 LLM Configuration",
            border_style="magenta",
        ))
    else:
        console.print("[dim]LLM not configured. Use 'journal llm set' to enable LLM-powered analysis.[/]")


# ── LLM Config Commands ─────────────────────────────────────────────

@cli.group()
def llm():
    """🤖 Configure LLM provider for enhanced analysis."""
    pass


@llm.command("set")
@click.option("--provider", "-p", required=True,
              type=click.Choice(["openai", "ollama", "gemini", "vllm"]),
              help="LLM provider")
@click.option("--model", "-m", required=True, help="Model name (e.g., gpt-4o, llama3, gemini-2.0-flash)")
@click.option("--base-url", "-u", default=None, help="Custom API base URL (required for vLLM, optional for others)")
@click.option("--temperature", "-t", default=0.3, help="Temperature (0.0-1.0)")
@click.option("--max-tokens", default=1024, help="Max output tokens")
def llm_set(provider: str, model: str, base_url: str | None, temperature: float, max_tokens: int):
    """Set LLM provider configuration."""
    config = LLMConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    save_llm_config(config)
    console.print(f"[green]✓ LLM configured:[/] [bold]{provider}[/] / [bold]{model}[/]")

    # Show env var hint for API keys
    if provider == "openai":
        console.print("  [dim]Set OPENAI_API_KEY environment variable for authentication.[/]")
    elif provider == "gemini":
        console.print("  [dim]Set GEMINI_API_KEY environment variable for authentication.[/]")
    elif provider == "vllm":
        if not base_url:
            console.print("  [yellow]⚠ vLLM requires --base-url. Use 'journal llm set' again with --base-url.[/]")


@llm.command("show")
def llm_show():
    """Show current LLM configuration."""
    config = load_llm_config()
    if not config:
        console.print("[yellow]No LLM configured. Use 'journal llm set' to configure.[/]")
        console.print()
        console.print("[bold]Examples:[/]")
        console.print("  journal llm set -p openai -m gpt-4o")
        console.print("  journal llm set -p ollama -m llama3")
        console.print("  journal llm set -p gemini -m gemini-2.0-flash")
        console.print("  journal llm set -p vllm -m meta-llama/Llama-3-8b -u http://gpu-server:8000/v1")
        return

    console.print(Panel(
        "\n".join([
            f"[bold magenta]Provider:[/]     {config.provider}",
            f"[bold magenta]Model:[/]        {config.model}",
            f"[bold magenta]Base URL:[/]     {config.base_url or 'default'}",
            f"[bold magenta]Temperature:[/]  {config.temperature}",
            f"[bold magenta]Max Tokens:[/]   {config.max_tokens}",
        ]),
        title="🤖 LLM Configuration",
        border_style="magenta",
    ))


@llm.command("test")
def llm_test():
    """Test the configured LLM with a simple prompt."""
    config = load_llm_config()
    if not config:
        console.print("[red]No LLM configured. Use 'journal llm set' first.[/]")
        return

    console.print(f"[cyan]Testing {config.provider}/{config.model}...[/]")
    try:
        llm_instance = create_llm(config)
        result = llm_instance.generate(
            "What is the most important recent advancement in AI research? Answer in one sentence."
        )
        console.print(Panel(result, title="✅ LLM Response", border_style="green"))
    except Exception as e:
        console.print(f"[red]✗ LLM test failed:[/] {e}")


@llm.command("remove")
def llm_remove():
    """Remove LLM configuration (revert to rule-based analysis)."""
    from .llm.factory import CONFIG_PATH
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        console.print("[green]✓ LLM configuration removed. Analysis will use rule-based methods.[/]")
    else:
        console.print("[yellow]No LLM configuration to remove.[/]")


if __name__ == "__main__":
    cli()
