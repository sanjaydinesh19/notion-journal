from openai import OpenAI

_SYSTEM = """\
You format raw voice journal transcripts into clean bullet points.
Rules:
- Remove all filler words: um, uh, like, you know, so, basically, right, okay
- Keep every meaningful piece of information — do not summarise or drop content
- Each bullet = one distinct event, thought, task, or accomplishment
- Write in first person, past or present tense, natural tone
- Return ONLY the bullet lines, each starting with "- "
- No headers, no extra commentary, no blank lines between bullets"""


def format_transcript(transcript: str, api_key: str) -> list[str]:
    """
    Returns a list of clean bullet strings (without the leading "- ").
    Falls back to a single raw bullet if the API call fails.
    """
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM},
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
