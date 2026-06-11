from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from notion_client import Client
from rich.console import Console

console = Console()


def _heading(text: str, level: int = 2) -> dict:
    tag = f"heading_{level}"
    return {"object": "block", "type": tag, tag: {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _paragraph(text: str = "") -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}] if text else []},
    }


def _bullet(text: str = "") -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _daily_blocks(transcript: str) -> list[dict]:
    return [
        _heading("Morning Check-in", 2),
        _bullet("Mood: "),
        _bullet("Energy Level: "),
        _divider(),
        _heading("Voice Entry", 2),
        _paragraph(transcript),
        _divider(),
        _heading("Key Accomplishments", 2),
        _bullet(""),
        _divider(),
        _heading("Gratitude", 2),
        _bullet(""),
        _divider(),
        _heading("Tomorrow's Focus", 2),
        _bullet(""),
    ]


def _weekly_blocks(week_start: date) -> list[dict]:
    week_end = week_start + timedelta(days=6)
    period = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    return [
        _paragraph(f"Week of {period}"),
        _divider(),
        _heading("This Week's Highlights", 2),
        _bullet(""),
        _divider(),
        _heading("Challenges Faced", 2),
        _bullet(""),
        _divider(),
        _heading("Lessons Learned", 2),
        _bullet(""),
        _divider(),
        _heading("Goals for Next Week", 2),
        _bullet(""),
        _divider(),
        _heading("Wins to Celebrate", 2),
        _bullet(""),
    ]


def _monthly_blocks(month: int, year: int) -> list[dict]:
    import calendar
    month_name = calendar.month_name[month]
    return [
        _paragraph(f"{month_name} {year}"),
        _divider(),
        _heading("Theme for the Month", 2),
        _paragraph(""),
        _divider(),
        _heading("Key Goals", 2),
        _bullet(""),
        _bullet(""),
        _bullet(""),
        _divider(),
        _heading("Habits to Build", 2),
        _bullet(""),
        _divider(),
        _heading("Skills to Develop", 2),
        _bullet(""),
        _divider(),
        _heading("Monthly Review", 2),
        _heading("What went well?", 3),
        _paragraph(""),
        _heading("What can be improved?", 3),
        _paragraph(""),
        _heading("Overall Rating", 3),
        _paragraph("/10"),
    ]


class NotionJournal:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token)
        self.database_id = database_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_daily_entry(self, transcript: str, entry_date: Optional[date] = None) -> str:
        entry_date = entry_date or date.today()
        title = f"Daily Journal – {entry_date.strftime('%B %d, %Y')}"

        if self._entry_exists(title):
            console.print(f"[yellow]Entry already exists:[/] {title}")
            return ""

        blocks = self._get_template_blocks("daily") or _daily_blocks(transcript)

        # If we cloned a template, inject the transcript into the Voice Entry section
        if self._get_template_blocks("daily"):
            blocks = _daily_blocks(transcript)

        page = self._create_page(title, entry_date, blocks)
        url = page.get("url", "")
        console.print(f"[bold green]Created daily entry:[/] {title}\n{url}")
        return url

    def create_weekly_entry(self, week_start: Optional[date] = None) -> str:
        if week_start is None:
            today = date.today()
            # Most recent Monday
            week_start = today - timedelta(days=today.weekday())

        title = f"Weekly Reflection – {week_start.strftime('%B %d, %Y')}"

        if self._entry_exists(title):
            console.print(f"[yellow]Entry already exists:[/] {title}")
            return ""

        blocks = _weekly_blocks(week_start)
        page = self._create_page(title, week_start, blocks)
        url = page.get("url", "")
        console.print(f"[bold green]Created weekly entry:[/] {title}\n{url}")
        return url

    def create_monthly_entry(self, month: Optional[int] = None, year: Optional[int] = None) -> str:
        today = date.today()
        month = month or today.month
        year = year or today.year
        import calendar
        title = f"Monthly Goals – {calendar.month_name[month]} {year}"

        if self._entry_exists(title):
            console.print(f"[yellow]Entry already exists:[/] {title}")
            return ""

        entry_date = date(year, month, 1)
        blocks = _monthly_blocks(month, year)
        page = self._create_page(title, entry_date, blocks)
        url = page.get("url", "")
        console.print(f"[bold green]Created monthly entry:[/] {title}\n{url}")
        return url

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _create_page(self, title: str, entry_date: date, blocks: list[dict]) -> dict:
        props = self._build_properties(title, entry_date)
        return self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=props,
            children=blocks,
        )

    def _build_properties(self, title: str, entry_date: date) -> dict:
        """Build properties dict. Tries common date property names."""
        db = self.client.databases.retrieve(self.database_id)
        props = db.get("properties", {})

        date_key = next(
            (k for k, v in props.items() if v["type"] == "date"),
            None,
        )
        title_key = next(
            (k for k, v in props.items() if v["type"] == "title"),
            "Name",
        )

        result: dict = {
            title_key: {"title": [{"type": "text", "text": {"content": title}}]},
        }
        if date_key:
            result[date_key] = {"date": {"start": entry_date.isoformat()}}

        return result

    def _entry_exists(self, title: str) -> bool:
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={
                "property": "Name",
                "title": {"equals": title},
            },
        )
        return len(response.get("results", [])) > 0

    def _get_template_blocks(self, entry_type: str) -> list[dict] | None:
        """Reserved for future: clone blocks from a user-provided template page."""
        return None
