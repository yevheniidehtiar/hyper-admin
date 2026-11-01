#!/usr/bin/env bash
# Wrapper for the gitpm CLI, pinned to the same release CI uses (.github/workflows/gitpm-sync.yml).
# Usage: ./scripts/gitpm.sh <command> [args...]
# Example: ./scripts/gitpm.sh validate
#
# `push` and `sync` are refused: the GitPM Sync workflow pushes .meta/ to GitHub after every merge
# to develop and keeps the sync state on the `gitpm-state` branch. A local push would use a
# different state and can create duplicate issues. Set GITPM_ALLOW_LOCAL_PUSH=1 to override.

set -euo pipefail

GITPM_CLI_VERSION="0.1.15"
GITPM_GITHUB_VERSION="0.1.12"

case "${1:-}" in
  push|sync)
    if [[ "${GITPM_ALLOW_LOCAL_PUSH:-}" != "1" ]]; then
      echo "gitpm $1 runs in CI (GitPM Sync workflow) after merges to develop." >&2
      echo "Merge your .meta/ change to develop instead, or set GITPM_ALLOW_LOCAL_PUSH=1." >&2
      exit 1
    fi
    ;;
esac

exec npx --yes \
  -p "@gitpm/cli@${GITPM_CLI_VERSION}" \
  -p "@gitpm/sync-github@${GITPM_GITHUB_VERSION}" \
  gitpm --meta-dir .meta "$@"
