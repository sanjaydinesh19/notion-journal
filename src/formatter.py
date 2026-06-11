from openai import OpenAI

_BULLET_SYSTEM = """\
You format raw voice journal transcripts into clean bullet points.
Rules:
- Remove all filler words: um, uh, like, you know, so, basically, right, okay
- Keep every meaningful piece of information — do not summarise or drop content
- Each bullet = one distinct event, thought, task, or accomplishment
- Write in first person, past or present tense, natural tone
- Return ONLY the bullet lines, each starting with "- "
- No headers, no extra commentary, no blank lines between bullets"""

_WEEKLY_SYSTEM = """\
You write weekly journal reflections from a list of daily journal entries.
Tone: personal, honest, first-person.
Structure your output EXACTLY as:

SUMMARY
<2–3 sentences covering the main themes and activities of the week>

HIGHLIGHTS
- <most significant thing 1>
- <most significant thing 2>
- <most significant thing 3>
(3–5 highlights only — the most meaningful ones, not every detail)

REFLECTION
<1–2 sentences: what went well, what you want to carry forward or improve>"""

_MONTHLY_SYSTEM = """\
You generate a personalised goals checklist for the upcoming month based on a person's recent journal entries.
Analyse patterns: unfinished work, recurring themes, growth areas, things they want to do.
Output ONLY a plain list of 5–8 specific, actionable goals — no headers, no commentary.
Each line: - <goal>
Goals should be concrete enough to tick off in a month."""


def format_transcript(transcript: str, api_key: str) -> list[str]:
    """Returns a list of clean bullet strings (without the leading dash)."""
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _BULLET_SYSTEM},
                {"role": "user", "content": transcript},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        lines = resp.choices[0].message.content.strip().splitlines()
        bullets = [l.lstrip("- •").strip() for l in lines if l.strip()]
        return bullets if bullets else [transcript]
    except Exception:
        return [transcript]


def generate_weekly_summary(entries: list[dict], api_key: str) -> dict:
    """
    entries: [{date: str, bullets: [str]}, ...]
    Returns {"notion_blocks": [...], "markdown": str}
    """
    if not entries:
        return {"notion_blocks": [], "markdown": ""}

    entries_text = "\n\n".join(
        f"{e['date']}:\n" + "\n".join(f"  - {b}" for b in e["bullets"])
        for e in entries
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _WEEKLY_SYSTEM},
                {"role": "user", "content": entries_text},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
    except Exception as e:
        raw = f"(Could not generate summary: {e})"

    return _parse_weekly(raw)


def generate_monthly_goals(entries: list[dict], api_key: str, month_name: str) -> dict:
    """
    entries: [{date: str, bullets: [str]}, ...]
    Returns {"notion_blocks": [...], "markdown": str}
    """
    if not entries:
        return {"notion_blocks": [], "markdown": ""}

    entries_text = "\n\n".join(
        f"{e['date']}:\n" + "\n".join(f"  - {b}" for b in e["bullets"])
        for e in entries
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _MONTHLY_SYSTEM},
                {"role": "user", "content": f"Generate goals for {month_name} based on these entries:\n\n{entries_text}"},
            ],
            temperature=0.4,
            max_tokens=400,
        )
        raw = resp.choices[0].message.content.strip()
    except Exception as e:
        raw = f"- (Could not generate goals: {e})"

    return _parse_monthly(raw, month_name)


# ---------------------------------------------------------------------------
# Parsers → Notion blocks + Markdown
# ---------------------------------------------------------------------------

def _h1(text):
    return {"object": "block", "type": "heading_1",
            "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _para(text):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}] if text else []}}


def _bullet(text):
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _todo(text):
    return {"object": "block", "type": "to_do",
            "to_do": {"rich_text": [{"type": "text", "text": {"content": text}}], "checked": False}}


def _divider():
    return {"object": "block", "type": "divider", "divider": {}}


def _parse_weekly(raw: str) -> dict:
    sections = {"SUMMARY": "", "HIGHLIGHTS": [], "REFLECTION": ""}
    current = None
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped in ("SUMMARY", "HIGHLIGHTS", "REFLECTION"):
            current = stripped
        elif current == "SUMMARY" and stripped:
            sections["SUMMARY"] += (" " if sections["SUMMARY"] else "") + stripped
        elif current == "HIGHLIGHTS" and stripped.startswith("-"):
            sections["HIGHLIGHTS"].append(stripped.lstrip("- ").strip())
        elif current == "REFLECTION" and stripped:
            sections["REFLECTION"] += (" " if sections["REFLECTION"] else "") + stripped

    blocks = []
    if sections["SUMMARY"]:
        blocks += [_h1("Summary"), _para(sections["SUMMARY"]), _divider()]
    if sections["HIGHLIGHTS"]:
        blocks += [_h1("Highlights")] + [_bullet(b) for b in sections["HIGHLIGHTS"]] + [_divider()]
    if sections["REFLECTION"]:
        blocks += [_h1("Reflection"), _para(sections["REFLECTION"])]

    md_lines = []
    if sections["SUMMARY"]:
        md_lines += ["## Summary", sections["SUMMARY"], ""]
    if sections["HIGHLIGHTS"]:
        md_lines += ["## Highlights"] + [f"- {b}" for b in sections["HIGHLIGHTS"]] + [""]
    if sections["REFLECTION"]:
        md_lines += ["## Reflection", sections["REFLECTION"]]

    return {"notion_blocks": blocks, "markdown": "\n".join(md_lines)}


def _parse_monthly(raw: str, month_name: str) -> dict:
    goals = [l.lstrip("- •").strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("#")]
    goals = [g for g in goals if g]

    blocks = [_h1(f"Goals for {month_name}"), _divider()] + [_todo(g) for g in goals]

    md_lines = [f"## Goals for {month_name}", ""] + [f"- [ ] {g}" for g in goals]

    return {"notion_blocks": blocks, "markdown": "\n".join(md_lines)}
