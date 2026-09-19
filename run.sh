#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/profile-availability"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

. "$VENV_DIR/bin/activate"

python -m pip install --quiet --upgrade pip
python -m pip install --quiet --requirement "$APP_DIR/requirements.txt"

mkdir -p "$LOG_DIR"

nohup python "$APP_DIR/profile-availability.py" >>"$LOG_DIR/run.log" 2>&1 &
disown

echo "profile-availability started (pid $!), logging to $LOG_DIR/run.log"
