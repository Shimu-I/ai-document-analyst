#!/usr/bin/env bash
# Starts the desktop window from the project folder, using .venv when it exists.
#   bash scripts/run_desktop.sh [file]
cd "$(dirname "$0")/.." || exit 1
[ -f .venv/bin/activate ] && . .venv/bin/activate
python3 -c "import tkinter" 2>/dev/null || { echo "Tkinter is missing: sudo apt install python3-tk"; exit 1; }
exec python3 app/desktop.py "$@"
