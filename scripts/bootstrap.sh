#!/usr/bin/env bash
set -euo pipefail

echo "==> Bootstrapping development environment..."

# Check for just
if ! command -v just &> /dev/null; then
    echo "==> Installing just..."
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "==> Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Sync dependencies
uv sync --all-extras

echo "✓ Development environment ready"
echo "  Run 'just' to see available targets"
