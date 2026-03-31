#!/usr/bin/env bash
set -euo pipefail

# Packaging defaults are tuned for AWS Lambda.
# Use LAMBDA_INSTALL_TARGET=host for local development on the current machine.
LAMBDA_INSTALL_TARGET="${LAMBDA_INSTALL_TARGET:-lambda}"
LAMBDA_TARGET_OS="${LAMBDA_TARGET_OS:-linux}"
LAMBDA_TARGET_ARCH="${LAMBDA_TARGET_ARCH:-x64}"

echo "Building PWA into lambda/dist..."
pushd src >/dev/null
npm install
npm run build
popd >/dev/null

echo "Installing lambda dependencies..."
pushd lambda >/dev/null
# When INSTALL_DEV_DEPS=1 is set we include devDependencies (useful for local development with nodemon).
if [ "$LAMBDA_INSTALL_TARGET" = "host" ]; then
    echo "Installing host-native dependencies for local development..."
    if [ "${INSTALL_DEV_DEPS:-0}" = "1" ]; then
        npm ci
    else
        npm ci --omit=dev
    fi
else
    echo "Installing Lambda-target dependencies for ${LAMBDA_TARGET_OS}/${LAMBDA_TARGET_ARCH}..."
    # Ensure stale host-native binaries cannot leak into the package.
    rm -rf node_modules
    # Install JS deps without running lifecycle scripts, then manually invoke
    # prebuild-install for sqlite3 with the correct target arch/platform.
    # This avoids npm "Unknown env config" warnings from npm_config_* env vars.
    if [ "${INSTALL_DEV_DEPS:-0}" = "1" ]; then
        npm ci --ignore-scripts
    else
        npm ci --omit=dev --ignore-scripts
    fi
    (cd node_modules/sqlite3 && npx prebuild-install -r napi \
        --arch "$LAMBDA_TARGET_ARCH" --platform "$LAMBDA_TARGET_OS" --libc glibc)
fi
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
