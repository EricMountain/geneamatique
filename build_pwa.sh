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

echo "Build complete. The lambda/dist directory contains the built site and lambda has node dependencies."
