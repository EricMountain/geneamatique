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

# Helper: find PIDs (and commands) listening on a given port
find_listeners_by_port() {
    local port=$1
    # Output lines: "PID COMMAND"
    if command -v lsof >/dev/null 2>&1; then
        # lsof: LISTEN entries; output PID and COMMAND
        lsof -i :"${port}" -sTCP:LISTEN -n -P 2>/dev/null | awk 'NR>1 { print $2 " " $1 }' || true
    else
        # Fallback to ss: parse pid/program:PID/name
        ss -ltnp 2>/dev/null | awk -v p=":${port}" '$4 ~ p { match($0, /pid=([0-9]+),?/, m); pid=m[1]; cmd=""; if (pid) { cmd="(unknown)"; } if (pid) print pid " " cmd }' || true
    fi
}

# Helper: gracefully kill a list of pids (only those that are allowed/unambiguous)
kill_pids() {
    local pids="$1"
    if [ -z "$pids" ]; then
        return 0
    fi
    echo "Killing existing process(es): $pids"
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    # Give them a moment to exit
    sleep 0.5
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "Process $pid did not exit; sending SIGKILL"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
}

# Check and clear any existing servers that may conflict (only target known server commands)
# Backend default port used by dev server
BACK_PORT=${BACK_PORT:-3001}
FORCE_KILL=${FORCE_KILL:-0}
EXISTING_BACK_LIST=$(find_listeners_by_port "$BACK_PORT")
if [ -n "$EXISTING_BACK_LIST" ]; then
    echo "Found existing backend listeners on port $BACK_PORT:"
    echo "$EXISTING_BACK_LIST"
    # Only kill processes whose command looks like one of the expected server commands
    ALLOWED='node|npm|nodejs|vite|python|dev_server|nodejs'
    BACK_PIDS_TO_KILL=""
    while read -r pid cmd; do
        # If cmd is blank (ss fallback), try to look up comm via /proc
        if [ -z "$cmd" ] || [ "$cmd" = "(unknown)" ]; then
            if [ -r "/proc/$pid/comm" ]; then
                cmd=$(cat "/proc/$pid/comm" 2>/dev/null || echo "(unknown)")
            fi
        fi
        if echo "$cmd" | egrep -i -q "$ALLOWED"; then
            BACK_PIDS_TO_KILL="$BACK_PIDS_TO_KILL $pid"
        else
            echo "  Skipping PID $pid (command: $cmd) — not in allowed list"
        fi
    done <<< "$EXISTING_BACK_LIST"
    if [ -n "$BACK_PIDS_TO_KILL" ]; then
        kill_pids "$BACK_PIDS_TO_KILL"
    fi
    # If FORCE_KILL is set, forcibly kill everything (useful in CI or when you really want to clear)
    if [ "$FORCE_KILL" = "1" ]; then
        echo "Force kill enabled; killing any remaining listeners on port $BACK_PORT"
        echo "$EXISTING_BACK_LIST" | awk '{print $1}' | xargs -r kill -TERM || true
        sleep 0.3
        echo "$EXISTING_BACK_LIST" | awk '{print $1}' | xargs -r kill -KILL || true
    fi
fi

# Frontend default Vite port
FRONT_PORT=${FRONT_PORT:-5173}
EXISTING_FRONT_LIST=$(find_listeners_by_port "$FRONT_PORT")
if [ -n "$EXISTING_FRONT_LIST" ]; then
    echo "Found existing frontend listeners on port $FRONT_PORT:"
    echo "$EXISTING_FRONT_LIST"
    ALLOWED='node|npm|nodejs|vite|python|dev_server|nodejs|browser-sync'
    FRONT_PIDS_TO_KILL=""
    while read -r pid cmd; do
        if [ -z "$cmd" ] || [ "$cmd" = "(unknown)" ]; then
            if [ -r "/proc/$pid/comm" ]; then
                cmd=$(cat "/proc/$pid/comm" 2>/dev/null || echo "(unknown)")
            fi
        fi
        if echo "$cmd" | egrep -i -q "$ALLOWED"; then
            FRONT_PIDS_TO_KILL="$FRONT_PIDS_TO_KILL $pid"
        else
            echo "  Skipping PID $pid (command: $cmd) — not in allowed list"
        fi
    done <<< "$EXISTING_FRONT_LIST"
    if [ -n "$FRONT_PIDS_TO_KILL" ]; then
        kill_pids "$FRONT_PIDS_TO_KILL"
    fi
    if [ "$FORCE_KILL" = "1" ]; then
        echo "Force kill enabled; killing any remaining listeners on port $FRONT_PORT"
        echo "$EXISTING_FRONT_LIST" | awk '{print $1}' | xargs -r kill -TERM || true
        sleep 0.3
        echo "$EXISTING_FRONT_LIST" | awk '{print $1}' | xargs -r kill -KILL || true
    fi
fi

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
