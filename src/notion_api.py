from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from notion_client import Client
from rich.console import Console

from . import config

console = Console()


def _tz() -> ZoneInfo:
    return ZoneInfo(config.get("SCHEDULER_TIMEZONE", "Asia/Kolkata"))


def _now_time_str() -> str:
    return datetime.now(_tz()).strftime("%I:%M %p").lstrip("0")


def _h1(text: str) -> dict:
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _paragraph(text: str = "") -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}] if text else []}}


def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _entry_blocks(time_str: str, bullets: list[str]) -> list[dict]:
    """A timestamped block of bullets — used for both create and append."""
    return [_h2(time_str), _divider()] + [_bullet(b) for b in bullets]


def _weekly_blocks() -> list[dict]:
    return [
        _h1("What went well this week?"),
        _bullet(""),
        _h1("Challenges"),
        _bullet(""),
        _h1("Lessons learned"),
        _bullet(""),
        _h1("Goals for next week"),
        _bullet(""),
    ]


def _monthly_blocks(month: int, year: int) -> list[dict]:
    return [
        _h1(f"Goals for {calendar.month_name[month]}"),
        _bullet(""),
        _h1("Habits to build"),
        _bullet(""),
        _h1("Skills to develop"),
        _bullet(""),
        _h1("End-of-month review"),
        _paragraph(""),
    ]


class NotionJournal:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token)
        self.database_id = database_id

    # ------------------------------------------------------------------
    # Daily — create or append
    # ------------------------------------------------------------------

    def add_daily_entry(self, bullets: list[str], entry_date: Optional[date] = None) -> str:
        entry_date = entry_date or date.today()
        time_str = _now_time_str()
        blocks = _entry_blocks(time_str, bullets)

        existing = self._find_entry("Daily Journal", entry_date)

        if existing:
            page_id = existing["id"]
            # Append a divider + new timestamped block to the existing page
            self.client.blocks.children.append(
                block_id=page_id,
                children=[_divider()] + blocks,
            )
            url = existing.get("url", "")
            console.print(f"[bold green]Appended to existing Daily Journal — {time_str}[/]\n{url}")
            return url
        else:
            page = self._create_page("Daily Journal", entry_date, blocks)
            url = page.get("url", "")
            console.print(f"[bold green]Created Daily Journal — {entry_date} @ {time_str}[/]\n{url}")
            return url

    # ------------------------------------------------------------------
    # Weekly / Monthly — create once, skip if exists
    # ------------------------------------------------------------------

    def create_weekly_entry(self, week_start: Optional[date] = None) -> str:
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        if self._find_entry("Weekly Reflection", week_start):
            console.print(f"[yellow]Weekly Reflection already exists for week of {week_start}[/]")
            return ""

        page = self._create_page("Weekly Reflection", week_start, _weekly_blocks())
        url = page.get("url", "")
        console.print(f"[bold green]Created Weekly Reflection — week of {week_start}[/]\n{url}")
        return url

    def create_monthly_entry(self, month: Optional[int] = None, year: Optional[int] = None) -> str:
        today = date.today()
        month = month or today.month
        year = year or today.year
        entry_date = date(year, month, 1)

        if self._find_entry("Monthly Goals", entry_date):
            console.print(f"[yellow]Monthly Goals already exists for {calendar.month_name[month]} {year}[/]")
            return ""

        page = self._create_page("Monthly Goals", entry_date, _monthly_blocks(month, year))
        url = page.get("url", "")
        console.print(f"[bold green]Created Monthly Goals — {calendar.month_name[month]} {year}[/]\n{url}")
        return url

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_page(self, title: str, entry_date: date, blocks: list[dict]) -> dict:
        return self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Name": {"title": [{"type": "text", "text": {"content": title}}]},
                "Date": {"date": {"start": entry_date.isoformat()}},
            },
            children=blocks,
        )

    def _find_entry(self, title: str, entry_date: date) -> Optional[dict]:
        """Return the first page matching title on entry_date, or None."""
        # Query by title then filter by date client-side (Notion date filter is unreliable)
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={"property": "Name", "title": {"equals": title}},
        )
        for page in response.get("results", []):
            d = (page["properties"].get("Date", {}).get("date") or {}).get("start", "")
            if d.startswith(entry_date.isoformat()):
                return page
        return None
