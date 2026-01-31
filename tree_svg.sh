#!/usr/bin/env bash

set -euo pipefail

. .venv/bin/activate

python -m import_tools.tree_to_json "$@" --db data/genealogy.db --out ui/demo_tree.json --pretty
cd ui
python -m http.server &
server_pid=$!

echo server started with PID $server_pid

sleep 1
echo open browser at http://localhost:8000/tree_viewer.html

# wait for user input
read -p "Press [Enter] key to stop the server and exit..." || true

kill $server_pid || true
wait $server_pid || true
echo "Server stopped."
