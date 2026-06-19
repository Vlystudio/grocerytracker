"""Command-line entry point.

Examples:
    python -m agent.main run                 # crawl all enabled sources once
    python -m agent.main run --source <id>   # crawl a single source
    python -m agent.main schedule            # run forever: daily + manual queue
    python -m agent.main seed-sources        # load config/sites.example.yaml -> DB
    python -m agent.main list-sources        # show configured sources
    python -m agent.main test-ai             # report which AI provider is active
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from .ai.extractor import AIExtractor
from .db import Database
from .logging_conf import get_logger
from .models import SiteConfig
from .pipeline import execute_run, run_all
from .scheduler import start_scheduler

app = typer.Typer(add_completion=False, help="Local research scraping agent.")
console = Console()
log = get_logger(__name__)


@app.command()
def run(
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Source UUID to crawl (default: all enabled)."
    )
) -> None:
    """Run a crawl immediately (manual trigger from your PC)."""
    db = Database()
    if source:
        run_id = db.start_run(source_id=source, trigger="manual")
        stats = execute_run(db, run_id, source_id=source)
    else:
        stats = run_all(db, trigger="manual")
    console.print(
        f"[green]Done.[/] new={stats.records_new} "
        f"found={stats.records_found} errors={stats.errors_count}"
    )


@app.command()
def schedule() -> None:
    """Start the long-running scheduler (daily crawl + manual-run queue)."""
    start_scheduler()


@app.command(name="seed-sources")
def seed_sources(
    file: Path = typer.Option(
        Path("config/sites.example.yaml"), "--file", "-f", help="YAML file to load."
    )
) -> None:
    """Upsert sources from a YAML file into Supabase."""
    if not file.exists():
        raise typer.BadParameter(f"File not found: {file}")
    data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    sources = data.get("sources", [])
    db = Database()
    for raw in sources:
        cfg = SiteConfig(**raw)
        db.upsert_source(cfg)
        console.print(f"[green]upserted[/] {cfg.name}")
    console.print(f"Seeded {len(sources)} source(s).")


@app.command(name="list-sources")
def list_sources() -> None:
    """List enabled sources currently configured in Supabase."""
    db = Database()
    sources = db.get_enabled_sources()
    table = Table(title="Enabled sources")
    table.add_column("Name")
    table.add_column("Engine")
    table.add_column("Depth")
    table.add_column("Base URL")
    table.add_column("ID", overflow="fold")
    for s in sources:
        table.add_row(s.name, s.engine, str(s.crawl_depth), s.base_url, s.id or "")
    console.print(table)


@app.command(name="test-ai")
def test_ai() -> None:
    """Show which AI provider(s) would be used for extraction."""
    ai = AIExtractor()
    if not ai.provider_order:
        console.print("[yellow]No AI provider available — parser-only mode.[/]")
    else:
        console.print("Provider order: " + " -> ".join(ai.provider_order))


@app.command(name="grocery-run")
def grocery_run() -> None:
    """Collect grocery deals (Flipp flyers + Whole Foods) for your ZIPs/stores."""
    from .collectors import run_grocery

    db = Database()
    stats = run_grocery(db, trigger="manual")
    console.print(
        f"[green]Done.[/] new={stats['new']} found={stats['found']} "
        f"sources={stats['flyers']} errors={stats['errors']}"
    )


@app.command(name="grocery-status")
def grocery_status() -> None:
    """Show configured grocery locations, stores, and how many deals are stored."""
    db = Database()
    locations = db.get_enabled_locations()
    stores = db.get_enabled_stores()
    deal_count = (
        db.client.table("grocery_deals").select("id", count="exact").execute().count
    )

    loc_table = Table(title="Enabled locations")
    loc_table.add_column("Name")
    loc_table.add_column("ZIP")
    for loc in locations:
        loc_table.add_row(loc["name"], loc["postal_code"])
    console.print(loc_table)

    store_table = Table(title="Whitelisted stores")
    store_table.add_column("Store")
    store_table.add_column("Match key")
    for s in stores:
        store_table.add_row(s["display_name"], s["match_key"])
    console.print(store_table)

    console.print(f"Total deals stored: [bold]{deal_count}[/]")


if __name__ == "__main__":
    app()
