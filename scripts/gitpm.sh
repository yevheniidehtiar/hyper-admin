#!/usr/bin/env bash
# Wrapper for gitpm CLI (installed from source at /tmp/gitpm-install)
# Usage: ./scripts/gitpm.sh <command> [args...]
# Example: ./scripts/gitpm.sh pull --token "$GITHUB_TOKEN"

set -euo pipefail

GITPM_DIR="${GITPM_DIR:-/tmp/gitpm-install}"
GITPM_CLI="$GITPM_DIR/packages/cli/dist/index.js"

if [[ ! -f "$GITPM_CLI" ]]; then
  echo "gitpm not found at $GITPM_CLI"
  echo "Run: git clone https://github.com/yevheniidehtiar/gitpm.git $GITPM_DIR && cd $GITPM_DIR && bun install && bun run build"
  exit 1
fi

exec bun "$GITPM_CLI" --meta-dir .meta "$@"
