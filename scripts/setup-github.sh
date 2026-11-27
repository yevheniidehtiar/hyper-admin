#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

echo "==> Setting up GitHub repository labels in $REPO..."

# Sizing Labels
gh label create "size:S" --repo "$REPO" --color "C5DEF5" --description "1-2 hours effort" || true
gh label create "size:M" --repo "$REPO" --color "BFD4F2" --description "2-4 hours effort" || true
gh label create "size:L" --repo "$REPO" --color "A2C4EA" --description "4-8 hours effort" || true

# Planning & Lifecycle Labels
gh label create "epic"       --repo "$REPO" --color "7057FF" --description "Parent issue with sub-issues" || true
gh label create "community"  --repo "$REPO" --color "BFDADC" --description "From external contributor" || true
gh label create "superseded" --repo "$REPO" --color "CFD3D7" --description "Replaced by other work, will not be implemented" || true
gh label create "deferred"   --repo "$REPO" --color "CFD3D7" --description "Parked: not scheduled for now" || true
gh label create "released"   --repo "$REPO" --color "5319E7" --description "Shipped in a release" || true

echo "✓ GitHub labels configured for $REPO"
