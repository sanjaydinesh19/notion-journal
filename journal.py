#!/usr/bin/env python3
"""
Voice-to-Notion Journal
Usage:
  journal.py record          – record voice → daily journal entry
  journal.py weekly          – manually create this week's reflection
  journal.py monthly         – manually create this month's goals
  journal.py schedule        – start the background scheduler
"""

from __future__ import annotations

from datetime import date

import click
from rich.console import Console
from rich.panel import Panel

from src import config
from src.notion_api import NotionJournal

console = Console()


def _journal() -> NotionJournal:
    return NotionJournal(
        token=config.require("NOTION_TOKEN"),
        database_id=config.require("NOTION_DATABASE_ID"),
    )


@click.group()
def cli():
    """Voice-to-Notion journal — speak your thoughts, automate your pages."""
    pass


@cli.command()
@click.option("--duration", "-d", default=300, show_default=True,
              help="Max recording duration in seconds before auto-stop.")
@click.option("--date", "entry_date", default=None,
              help="Entry date in YYYY-MM-DD format (default: today).")
def record(duration: int, entry_date: str | None):
    """Record voice and create a Daily Journal entry in Notion."""
    from src.audio import record_audio, transcribe

    console.print(Panel.fit(
        "[bold]Notion Voice Journal[/]\nSpeak your daily reflection. Press [bold]Enter[/] when done.",
        border_style="green",
    ))

    audio_path = record_audio(max_duration=duration)
    console.print(f"[dim]Audio captured ({audio_path.stat().st_size // 1024} KB)[/]")

    api_key = config.require("OPENAI_API_KEY")
    transcript = transcribe(audio_path, api_key)

    console.print(Panel(transcript, title="[bold]Transcript[/]", border_style="blue"))

    parsed_date = date.fromisoformat(entry_date) if entry_date else None
    _journal().create_daily_entry(transcript, parsed_date)


@cli.command()
@click.option("--week-start", default=None,
              help="Week start date in YYYY-MM-DD format (default: most recent Monday).")
def weekly(week_start: str | None):
    """Create a Weekly Reflection entry in Notion."""
    parsed = date.fromisoformat(week_start) if week_start else None
    _journal().create_weekly_entry(parsed)


@cli.command()
@click.option("--month", default=None, type=int, help="Month number (1-12, default: current).")
@click.option("--year", default=None, type=int, help="Year (default: current).")
def monthly(month: int | None, year: int | None):
    """Create a Monthly Goals entry in Notion."""
    _journal().create_monthly_entry(month, year)


@cli.command()
def schedule():
    """Start the background scheduler (creates weekly/monthly entries automatically)."""
    from src.scheduler import start_scheduler
    start_scheduler()


@cli.command()
def check():
    """Verify that Notion credentials and database access are working."""
    console.print("[dim]Checking Notion connection...[/]")
    try:
        j = _journal()
        db = j.client.databases.retrieve(j.database_id)
        title = db.get("title", [{}])[0].get("plain_text", "(untitled)")
        console.print(f"[bold green]Connected![/] Database: [bold]{title}[/]")

        props = db.get("properties", {})
        console.print("\nDatabase properties:")
        for name, prop in props.items():
            console.print(f"  [dim]{prop['type']:15}[/] {name}")
    except Exception as e:
        console.print(f"[bold red]Connection failed:[/] {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
