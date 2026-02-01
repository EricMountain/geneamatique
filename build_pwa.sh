#!/usr/bin/env bash
set -euo pipefail

echo "Building PWA into lambda/dist..."
pushd src >/dev/null
npm install
npm run build
popd >/dev/null

echo "Installing lambda dependencies..."
pushd lambda >/dev/null
npm install --production
popd >/dev/null

# Copy SQLite DB into the lambda package if present (do NOT commit real DBs to repo)
if [ -f data/genealogy.db ]; then
    echo "Copying data/genealogy.db into lambda/dist/data/"
    mkdir -p lambda/dist/data
    cp data/genealogy.db lambda/dist/data/
else
    echo "No data/genealogy.db found — skip copying DB (you may inject one into lambda/dist/data/genealogy.db before deployment)"
fi

echo "Build complete. The lambda/dist directory contains the built site, lambda node deps, and (optionally) the database."
