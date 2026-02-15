#!/usr/bin/env bash
set -euo pipefail

# Watch for changes in the frontend `src/` or `lambda/` and re-run `./build_pwa.sh`.
# Prefer `inotifywait` when available (more efficient). If not found, use a simple polling fallback.

trap 'echo "Stopping watch"; exit 0' INT TERM

if command -v inotifywait >/dev/null 2>&1; then
    echo "Using inotifywait to watch changes. Press Ctrl-C to stop."
    # Run an initial build
    ./build_pwa.sh
    while true; do
        # Wait for a filesystem event
        inotifywait -r -e modify,create,delete,move --exclude '(^|/)(\.git|node_modules|lambda/dist)' src lambda build_pwa.sh >/dev/null 2>&1
        echo "Change detected — rebuilding..."
        ./build_pwa.sh
    done
else
    echo "inotifywait not found; falling back to a polling watcher (every 2s)."
    echo "Install inotify-tools for an efficient watcher (e.g., 'sudo apt install inotify-tools')."
    # Run an initial build
    ./build_pwa.sh
    LAST_TS=$(date +%s)
    while true; do
        sleep 2
        # Find any file newer than last recorded timestamp
        NEW=$(find src lambda build_pwa.sh -type f -newermt "@${LAST_TS}" | head -n1 || true)
        if [ -n "${NEW}" ]; then
            echo "Change detected (${NEW}) — rebuilding..."
            ./build_pwa.sh
            LAST_TS=$(date +%s)
        fi
    done
fi
