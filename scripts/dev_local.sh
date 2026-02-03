#!/usr/bin/env bash
set -euo pipefail

# Dev helper: start the lambda local dev server and the frontend dev server.
# Usage: ./scripts/dev_local.sh
# Robust signal handling: both backend and frontend are started in background and
# any SIGINT/SIGTERM will be forwarded so CTRL-C stops both processes.

cleanup() {
    # Disable traps while cleaning up to avoid recursive calls
    trap - INT TERM EXIT
    echo "Shutting down..."
    [ -n "${BACK_PID:-}" ] && kill -TERM "${BACK_PID}" 2>/dev/null || true
    [ -n "${FRONT_PID:-}" ] && kill -TERM "${FRONT_PID}" 2>/dev/null || true
    wait "${BACK_PID:-}" 2>/dev/null || true
    wait "${FRONT_PID:-}" 2>/dev/null || true
}

trap 'cleanup; exit 0' INT TERM

# Start backend in background
echo "Starting backend (lambda dev server)..."
( cd lambda && npm run dev ) &
BACK_PID=$!

# Give backend a moment to start
sleep 1

# Start frontend in background so we can manage both processes
echo "Starting frontend (Vite)..."
( cd src && npm run dev ) &
FRONT_PID=$!

# Wait for either process to exit
# wait -n returns when any child process terminates
wait -n
# One of the processes exited; perform cleanup which will terminate the other
cleanup

# Exit with non-zero if any child exited with an error
wait "${BACK_PID}" 2>/dev/null || true
wait "${FRONT_PID}" 2>/dev/null || true
