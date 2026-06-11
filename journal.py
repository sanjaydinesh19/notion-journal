#!/usr/bin/env python3
"""
Voice-to-Notion Journal
  journal.py record    – record voice → daily journal entry
  journal.py weekly    – manually create this week's reflection
  journal.py monthly   – manually create this month's goals
  journal.py schedule  – start the background scheduler
  journal.py check     – verify Notion connection
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
              help="Max recording duration in seconds.")
@click.option("--date", "entry_date", default=None,
              help="Entry date YYYY-MM-DD (default: today).")
def record(duration: int, entry_date: str | None):
    """Record voice, review transcript, then add to today's Daily Journal."""
    from src.audio import record_audio, transcribe
    from src.formatter import format_transcript

    openai_key = config.require("OPENAI_API_KEY")
    parsed_date = date.fromisoformat(entry_date) if entry_date else None

    while True:
        console.print(Panel.fit(
            "[bold]Notion Voice Journal[/]\nSpeak your entry. Press [bold]Enter[/] when done.",
            border_style="green",
        ))

        audio_path = record_audio(max_duration=duration)
        transcript = transcribe(audio_path, openai_key)

        console.print(Panel(transcript, title="[bold]Transcript[/]", border_style="blue"))

        console.print(
            "\n  [[bold green]Enter[/]] Save    "
            "[[bold yellow]R[/]] Re-record    "
            "[[bold red]N[/]] Cancel\n"
        )
        choice = input("  > ").strip().lower()

        if choice == "n":
            console.print("[yellow]Cancelled.[/]")
            return
        if choice == "r":
            continue

        # Format and save
        console.print("[dim]Formatting with AI...[/]")
        bullets = format_transcript(transcript, openai_key)

        console.print(Panel(
            "\n".join(f"• {b}" for b in bullets),
            title="[bold]Formatted Entry[/]",
            border_style="green",
        ))

        result = _journal().add_daily_entry(bullets, parsed_date)

        # GitHub backup
        gh_token = config.get("GITHUB_TOKEN")
        gh_repo = config.get("GITHUB_JOURNAL_REPO")
        if gh_token and gh_repo:
            try:
                from src.github_backup import JournalBackup
                backup = JournalBackup(gh_token, gh_repo)
                backup.commit(
                    entry_date=result["entry_date"],
                    daily_md=result["daily_md"],
                    weekly_md=result.get("weekly_md"),
                    monthly_md=result.get("monthly_md"),
                )
            except Exception as e:
                console.print(f"[yellow]GitHub backup failed:[/] {e}")

        return


@cli.command()
@click.option("--week-start", default=None, help="YYYY-MM-DD (default: most recent Monday).")
def weekly(week_start: str | None):
    """Create a Weekly Reflection entry in Notion."""
    parsed = date.fromisoformat(week_start) if week_start else None
    _journal().create_weekly_entry(parsed)


@cli.command()
@click.option("--month", default=None, type=int, help="Month 1-12 (default: current).")
@click.option("--year", default=None, type=int, help="Year (default: current).")
def monthly(month: int | None, year: int | None):
    """Create a Monthly Goals entry in Notion."""
    _journal().create_monthly_entry(month, year)


@cli.command()
def schedule():
    """Start the background scheduler (weekly/monthly auto-creation)."""
    from src.scheduler import start_scheduler
    start_scheduler()


@cli.command()
def check():
    """Verify Notion credentials and database access."""
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
