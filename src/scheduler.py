from __future__ import annotations

import signal
import sys
from datetime import date, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from rich.console import Console

from . import config
from .notion_api import NotionJournal

console = Console()

DAY_MAP = {
    "mon": "mon", "tue": "tue", "wed": "wed", "thu": "thu",
    "fri": "fri", "sat": "sat", "sun": "sun",
}


def _build_journal() -> NotionJournal:
    return NotionJournal(
        token=config.require("NOTION_TOKEN"),
        database_id=config.require("NOTION_DATABASE_ID"),
    )


def _weekly_job():
    console.print("[dim]Scheduler: creating weekly reflection...[/]")
    journal = _build_journal()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    journal.create_weekly_entry(week_start)


def _monthly_job():
    console.print("[dim]Scheduler: creating monthly goals...[/]")
    journal = _build_journal()
    today = date.today()
    journal.create_monthly_entry(today.month, today.year)


def start_scheduler():
    tz = config.get("SCHEDULER_TIMEZONE", "Asia/Kolkata")
    weekly_day = DAY_MAP.get(config.get("WEEKLY_ENTRY_DAY", "sun").lower(), "sun")
    weekly_time = config.get("WEEKLY_ENTRY_TIME", "20:00")
    monthly_time = config.get("MONTHLY_ENTRY_TIME", "09:00")

    w_hour, w_min = weekly_time.split(":")
    m_hour, m_min = monthly_time.split(":")

    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week=weekly_day, hour=int(w_hour), minute=int(w_min), timezone=tz),
        id="weekly",
        name="Weekly Reflection",
        replace_existing=True,
    )

    scheduler.add_job(
        _monthly_job,
        CronTrigger(day=1, hour=int(m_hour), minute=int(m_min), timezone=tz),
        id="monthly",
        name="Monthly Goals",
        replace_existing=True,
    )

    def _shutdown(sig, frame):
        console.print("\n[yellow]Scheduler shutting down...[/]")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    console.print(f"[bold green]Scheduler started[/] (timezone: {tz})")
    console.print(f"  Weekly Reflection: every {weekly_day.capitalize()} at {weekly_time}")
    console.print(f"  Monthly Goals:     1st of each month at {monthly_time}")
    console.print("\nPress Ctrl+C to stop.\n")

    scheduler.start()
