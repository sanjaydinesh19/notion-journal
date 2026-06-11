# Notion Voice Journal

Record your daily reflection by voice — it gets transcribed and added to your Notion Calendar Database automatically. Weekly Reflections and Monthly Goals pages are created on schedule.

## How it works

```
You speak → Whisper transcribes → Notion page created in your Calendar DB
                                      ↳ Daily Journal  (voice entry)
                                      ↳ Weekly Reflection  (auto, every Sunday)
                                      ↳ Monthly Goals      (auto, 1st of month)
```

## Setup

### 1. Install dependencies

```bash
chmod +x install.sh
./install.sh
```

This installs PortAudio (needed for microphone access), creates a `.venv`, and copies `.env.example` → `.env`.

### 2. Get your API keys

**Notion Integration Token:**
1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New Integration** → give it a name → Save
3. Copy the **Internal Integration Token** → paste as `NOTION_TOKEN` in `.env`
4. Open your Calendar Database in Notion → click `···` → **Add connections** → select your integration

**Notion Database ID:**
- Open your Notion database → look at the URL:
  `notion.so/workspace/`**`xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`**`?v=...`
- Copy that 32-character ID → paste as `NOTION_DATABASE_ID` in `.env`

**OpenAI API Key (for Whisper transcription):**
- Get from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Paste as `OPENAI_API_KEY` in `.env`

### 3. Verify connection

```bash
.venv/bin/python journal.py check
```

## Usage

### Record a daily journal entry

```bash
.venv/bin/python journal.py record
```

Speak freely. Press **Enter** when done. The transcript is shown, then the page is created in Notion.

Options:
```
--duration / -d   Max recording seconds before auto-stop (default: 300)
--date            Entry date as YYYY-MM-DD (default: today)
```

### Manually create weekly / monthly pages

```bash
.venv/bin/python journal.py weekly
.venv/bin/python journal.py monthly
```

### Start the auto-scheduler (background daemon)

```bash
.venv/bin/python journal.py schedule
```

Runs in the foreground. Creates:
- **Weekly Reflection** every Sunday at 20:00 (configurable in `.env`)
- **Monthly Goals** on the 1st of each month at 09:00 (configurable)

### Run scheduler as a systemd service (auto-start on boot)

```bash
cp notion-journal-scheduler.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now notion-journal-scheduler
systemctl --user status notion-journal-scheduler
```

## Page Templates

Each entry type has a built-in block structure:

| Type | Sections |
|------|----------|
| Daily Journal | Morning Check-in · Voice Entry · Key Accomplishments · Gratitude · Tomorrow's Focus |
| Weekly Reflection | Highlights · Challenges · Lessons Learned · Goals for Next Week · Wins |
| Monthly Goals | Theme · Key Goals · Habits · Skills · End-of-month Review |

The transcribed text lands in the **Voice Entry** section of the Daily Journal.

## Configuration (`.env`)

| Variable | Description |
|----------|-------------|
| `NOTION_TOKEN` | Notion integration token |
| `NOTION_DATABASE_ID` | Your Calendar database ID |
| `OPENAI_API_KEY` | For Whisper transcription |
| `SCHEDULER_TIMEZONE` | e.g. `Asia/Kolkata` |
| `WEEKLY_ENTRY_DAY` | `sun` / `mon` / … (default: `sun`) |
| `WEEKLY_ENTRY_TIME` | 24h `HH:MM` (default: `20:00`) |
| `MONTHLY_ENTRY_TIME` | 24h `HH:MM` (default: `09:00`) |

## Requirements

- Python 3.10+
- Linux with PulseAudio / PipeWire (standard on Ubuntu/Fedora)
- Microphone
