#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    echo "Usage: ./scripts/release.sh <version>"
    echo "  Example: ./scripts/release.sh 0.2.0"
    exit 1
fi

echo "==> Preparing release v${VERSION}..."

# Pre-flight checks
echo "  Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Working directory is not clean. Commit or stash changes first."
    exit 1
fi

echo "  Running lint..."
just lint

echo "  Running tests..."
just test

echo "  Tagging v${VERSION}..."
git tag -a "v${VERSION}" -m "Release v${VERSION}"
git push origin "v${VERSION}"

echo "✓ Released v${VERSION}"
echo "  GitHub Actions will handle package publishing."
