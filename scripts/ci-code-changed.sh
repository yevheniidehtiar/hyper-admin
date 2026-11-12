#!/usr/bin/env bash
# Decide whether a CI run needs the code checks (lint, tests, e2e).
#
# Prints `code=true` or `code=false` to $GITHUB_OUTPUT (stdout when unset).
# `false` only for a pull request whose every changed file is documentation, project
# planning (`.meta/`), agent configuration or a report. Everything else, every push and any
# doubt answer `true`, so a new kind of file runs the checks until it is listed here.
#
# Usage: scripts/ci-code-changed.sh <event-name> <base-ref>
# Needs a checkout with enough history to diff against origin/<base-ref>.
set -euo pipefail

event="${1:?event name}"
base="${2:-}"
out="${GITHUB_OUTPUT:-/dev/stdout}"

if [ "$event" != "pull_request" ] || [ -z "$base" ]; then
  echo "code=true" >> "$out"
  exit 0
fi

git fetch --no-tags --quiet origin "$base"
changed="$(git diff --name-only "origin/$base...HEAD")"

if [ -z "$changed" ]; then
  # No diff against the base (an empty commit, for instance): nothing to test.
  echo "code=false" >> "$out"
  exit 0
fi

# Anything not matching a non-code pattern counts as code.
if printf '%s\n' "$changed" | grep -v -E '^(\.meta/|docs/|\.claude/|reports/)|\.md$' | grep -q .; then
  echo "code=true" >> "$out"
else
  echo "code=false" >> "$out"
fi
