#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$APP_DIR/profile-availability.py"

if ! pkill -f "$SCRIPT"; then
    echo "profile-availability is not running"
    exit 0
fi

for _ in $(seq 1 10); do
    if ! pgrep -f "$SCRIPT" >/dev/null; then
        echo "profile-availability stopped"
        exit 0
    fi
    sleep 1
done

echo "profile-availability still running after 10 seconds" >&2
exit 1
