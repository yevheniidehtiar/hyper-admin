#!/usr/bin/env bash
set -euo pipefail

echo "==> Running linter..."
uv run ruff check . --fix
uv run ruff format .
echo "✓ Lint clean"
