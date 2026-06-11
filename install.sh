#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing system dependencies..."
sudo apt-get install -y portaudio19-dev python3-venv python3-dev 2>/dev/null || true

echo "==> Creating virtual environment..."
python3 -m venv "$PROJECT_DIR/.venv"

echo "==> Installing Python packages..."
"$PROJECT_DIR/.venv/bin/pip" install --upgrade pip
"$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "==> Setting up .env..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "   Created .env — please fill in your API keys before using."
else
    echo "   .env already exists, skipping."
fi

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your NOTION_TOKEN, NOTION_DATABASE_ID, and OPENAI_API_KEY"
echo "  2. Run: .venv/bin/python journal.py check    (verify Notion connection)"
echo "  3. Run: .venv/bin/python journal.py record   (record your first entry)"
echo ""
echo "To enable the auto-scheduler as a systemd service:"
echo "  cp notion-journal-scheduler.service ~/.config/systemd/user/"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now notion-journal-scheduler"
