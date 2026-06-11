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


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _h2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _entry_blocks(time_str: str, bullets: list[str]) -> list[dict]:
    return [_h2(time_str), _divider()] + [_bullet(b) for b in bullets]


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class NotionJournal:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token)
        self.database_id = database_id

    # ------------------------------------------------------------------
    # Daily — create or append, then trigger weekly + monthly updates
    # ------------------------------------------------------------------

    def add_daily_entry(
        self,
        bullets: list[str],
        entry_date: Optional[date] = None,
    ) -> dict:
        """
        Add a timestamped bullet block to today's Daily Journal (create if missing).
        Then regenerate the Weekly Reflection and Monthly Goals pages.
        Returns {"daily_url", "daily_md", "weekly_md", "monthly_md", "entry_date"}.
        """
        entry_date = entry_date or date.today()
        time_str = _now_time_str()
        blocks = _entry_blocks(time_str, bullets)

        existing = self._find_entry("Daily Journal", entry_date)
        if existing:
            self.client.blocks.children.append(
                block_id=existing["id"],
                children=[_divider()] + blocks,
            )
            daily_url = existing.get("url", "")
            console.print(f"[bold green]Appended to Daily Journal — {time_str}[/]\n{daily_url}")
        else:
            page = self._create_page("Daily Journal", entry_date, blocks)
            daily_url = page.get("url", "")
            console.print(f"[bold green]Created Daily Journal — {entry_date} @ {time_str}[/]\n{daily_url}")

        # Build markdown for the full day (re-fetch so it's complete)
        daily_md = self._daily_page_to_markdown(entry_date)

        # Auto-update weekly and monthly
        weekly_md = self._update_weekly(entry_date)
        monthly_md = self._update_monthly(entry_date)

        return {
            "daily_url": daily_url,
            "daily_md": daily_md,
            "weekly_md": weekly_md,
            "monthly_md": monthly_md,
            "entry_date": entry_date,
        }

    # ------------------------------------------------------------------
    # Weekly — auto-create/replace with AI summary
    # ------------------------------------------------------------------

    def _update_weekly(self, ref_date: date) -> str:
        from .formatter import generate_weekly_summary

        week_start = ref_date - timedelta(days=ref_date.weekday())
        entries = self._get_daily_content(since=week_start)

        if not entries:
            return ""

        openai_key = config.require("OPENAI_API_KEY")
        console.print("[dim]Generating weekly summary...[/]")
        result = generate_weekly_summary(entries, openai_key)
        blocks = result["notion_blocks"]

        if not blocks:
            return ""

        page = self._find_entry("Weekly Reflection", week_start)
        if page:
            self._replace_page_blocks(page["id"], blocks)
            url = page.get("url", "")
        else:
            page = self._create_page("Weekly Reflection", week_start, blocks)
            url = page.get("url", "")

        console.print(f"[dim]Updated Weekly Reflection[/] {url}")
        return result["markdown"]

    # ------------------------------------------------------------------
    # Monthly — auto-create/replace with AI goals checklist
    # ------------------------------------------------------------------

    def _update_monthly(self, ref_date: date) -> str:
        from .formatter import generate_monthly_goals

        month_start = date(ref_date.year, ref_date.month, 1)
        since = ref_date - timedelta(days=30)
        entries = self._get_daily_content(since=since)

        if not entries:
            return ""

        month_name = calendar.month_name[ref_date.month]
        openai_key = config.require("OPENAI_API_KEY")
        console.print("[dim]Generating monthly goals...[/]")
        result = generate_monthly_goals(entries, openai_key, month_name)
        blocks = result["notion_blocks"]

        if not blocks:
            return ""

        page = self._find_entry("Monthly Goals", month_start)
        if page:
            self._replace_page_blocks(page["id"], blocks)
            url = page.get("url", "")
        else:
            page = self._create_page("Monthly Goals", month_start, blocks)
            url = page.get("url", "")

        console.print(f"[dim]Updated Monthly Goals[/] {url}")
        return result["markdown"]

    # ------------------------------------------------------------------
    # Manual create commands (used by scheduler / CLI)
    # ------------------------------------------------------------------

    def create_weekly_entry(self, week_start: Optional[date] = None) -> str:
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        return self._update_weekly(week_start)

    def create_monthly_entry(self, month: Optional[int] = None, year: Optional[int] = None) -> str:
        today = date.today()
        ref = date(year or today.year, month or today.month, 1)
        return self._update_monthly(ref)

    # ------------------------------------------------------------------
    # Content helpers
    # ------------------------------------------------------------------

    def _get_daily_content(self, since: date) -> list[dict]:
        """Fetch daily journal entries since `since`, return [{date, bullets}]."""
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={"property": "Name", "title": {"equals": "Daily Journal"}},
        )
        entries = []
        for page in response.get("results", []):
            d_str = (page["properties"].get("Date", {}).get("date") or {}).get("start", "")
            if not d_str or d_str[:10] < since.isoformat():
                continue
            bullets = self._extract_bullets(page["id"])
            if bullets:
                entries.append({"date": d_str[:10], "bullets": bullets})

        return sorted(entries, key=lambda x: x["date"])

    def _extract_bullets(self, page_id: str) -> list[str]:
        """Extract all bulleted_list_item text from a page."""
        blocks = self.client.blocks.children.list(page_id)
        bullets = []
        for b in blocks.get("results", []):
            if b["type"] == "bulleted_list_item":
                rich = b["bulleted_list_item"].get("rich_text", [])
                text = "".join(r.get("plain_text", "") for r in rich).strip()
                if text:
                    bullets.append(text)
        return bullets

    def _daily_page_to_markdown(self, entry_date: date) -> str:
        """Build a markdown string from today's Daily Journal page blocks."""
        page = self._find_entry("Daily Journal", entry_date)
        if not page:
            return ""

        blocks = self.client.blocks.children.list(page["id"])
        lines = []
        for b in blocks.get("results", []):
            btype = b["type"]
            rich = b.get(btype, {}).get("rich_text", [])
            text = "".join(r.get("plain_text", "") for r in rich).strip()

            if btype == "heading_2" and text:
                lines.append(f"\n## {text}")
            elif btype == "bulleted_list_item" and text:
                lines.append(f"- {text}")
            elif btype == "divider":
                lines.append("---")

        return "\n".join(lines).strip()

    def _replace_page_blocks(self, page_id: str, new_blocks: list[dict]):
        """Delete all existing blocks on a page and append new_blocks."""
        existing = self.client.blocks.children.list(page_id)
        for block in existing.get("results", []):
            try:
                self.client.blocks.delete(block["id"])
            except Exception:
                pass
        if new_blocks:
            self.client.blocks.children.append(block_id=page_id, children=new_blocks)

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
        response = self.client.databases.query(
            database_id=self.database_id,
            filter={"property": "Name", "title": {"equals": title}},
        )
        for page in response.get("results", []):
            d = (page["properties"].get("Date", {}).get("date") or {}).get("start", "")
            if d.startswith(entry_date.isoformat()):
                return page
        return None
