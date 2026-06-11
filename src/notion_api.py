from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional

from notion_client import Client
from rich.console import Console

console = Console()


def _h1(text: str) -> dict:
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _paragraph(text: str = "") -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}] if text else []}}


def _bullet(text: str = "") -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _daily_blocks(transcript: str) -> list[dict]:
    return [
        _h1("Voice Entry"),
        _divider(),
        _paragraph(transcript),
        _h1("Academic Work"),
        _divider(),
        _bullet(""),
        _h1("Resume Work"),
        _divider(),
        _bullet(""),
        _h1("Personal"),
        _divider(),
        _bullet(""),
    ]


def _weekly_blocks() -> list[dict]:
    return [
        _h1("Weekly Progress"),
        _bullet(""),
        _h1("What went well?"),
        _bullet(""),
        _h1("What could be better?"),
        _bullet(""),
        _h1("Goals for next week"),
        _bullet(""),
    ]


def _monthly_blocks(month: int, year: int) -> list[dict]:
    month_name = calendar.month_name[month]
    return [
        _h1(f"Goals for {month_name} {year}"),
        _bullet(""),
        _h1("Habits to build"),
        _bullet(""),
        _h1("Skills to develop"),
        _bullet(""),
        _h1("End of month review"),
        _divider(),
        _paragraph(""),
    ]


class NotionJournal:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token)
        self.database_id = database_id

    def create_daily_entry(self, transcript: str, entry_date: Optional[date] = None) -> str:
        entry_date = entry_date or date.today()

        if self._entry_exists_on_date("Daily Journal", entry_date):
            console.print(f"[yellow]Daily Journal entry already exists for {entry_date}[/]")
            return ""

        page = self._create_page("Daily Journal", entry_date, _daily_blocks(transcript))
        url = page.get("url", "")
        console.print(f"[bold green]Created:[/] Daily Journal — {entry_date}\n{url}")
        return url

    def create_weekly_entry(self, week_start: Optional[date] = None) -> str:
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        if self._entry_exists_on_date("Weekly Reflection", week_start):
            console.print(f"[yellow]Weekly Reflection already exists for week of {week_start}[/]")
            return ""

        page = self._create_page("Weekly Reflection", week_start, _weekly_blocks())
        url = page.get("url", "")
        console.print(f"[bold green]Created:[/] Weekly Reflection — week of {week_start}\n{url}")
        return url

    def create_monthly_entry(self, month: Optional[int] = None, year: Optional[int] = None) -> str:
        today = date.today()
        month = month or today.month
        year = year or today.year
        entry_date = date(year, month, 1)

        if self._entry_exists_on_date("Monthly Goals", entry_date):
            console.print(f"[yellow]Monthly Goals already exists for {calendar.month_name[month]} {year}[/]")
            return ""

        page = self._create_page("Monthly Goals", entry_date, _monthly_blocks(month, year))
        url = page.get("url", "")
        console.print(f"[bold green]Created:[/] Monthly Goals — {calendar.month_name[month]} {year}\n{url}")
        return url

    def _create_page(self, title: str, entry_date: date, blocks: list[dict]) -> dict:
        return self.client.pages.create(
            parent={"database_id": self.database_id},
            properties={
                "Name": {"title": [{"type": "text", "text": {"content": title}}]},
                "Date": {"date": {"start": entry_date.isoformat()}},
            },
            children=blocks,
        )

    def _entry_exists_on_date(self, title: str, entry_date: date) -> bool:
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={
                "and": [
                    {"property": "Name", "title": {"equals": title}},
                    {"property": "Date", "date": {"equals": entry_date.isoformat()}},
                ]
            },
        )
        return len(response.get("results", [])) > 0
