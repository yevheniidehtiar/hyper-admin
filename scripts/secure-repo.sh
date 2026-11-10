#!/usr/bin/env bash
# Secure repository settings using GitHub CLI (gh)
#
# Usage:
#   scripts/secure-repo.sh epic-ruleset [owner/repo]
#       Print the 'epic-branches' ruleset payload. Makes no API call.
#   scripts/secure-repo.sh epic-ruleset --apply [owner/repo]
#       Create or update only the 'epic-branches' ruleset (owner identity).
#       Nothing else in the repo is touched.
#   scripts/secure-repo.sh [owner/repo]
#       Full run. This WRITES repo settings: default branch, security
#       toggles, delete-branch-on-merge. It does not touch the epic ruleset.
#       With APPLY_BRANCH_PROTECTION=1 it also creates or updates the legacy
#       'Branch Protection' ruleset; read the warning in section 2 first.
set -euo pipefail

# Epic branches ruleset (epic/<slug>, merged by the autopilot)
#
# Exactly one rule: required_linear_history. Squash is disabled repo-wide, so
# rebase is the only merge button left on story PRs. Deliberately absent:
#   - required_status_checks: would reject the bot's rebase force-push; the
#     autopilot tick gates merges on CI itself
#   - pull_request: would forbid the open/close-epic commits pushed directly
#   - non_fast_forward: the epic branch is rebased on develop with a force-push
#   - deletion: the branch is deleted when the epic PR merges
EPIC_RULESET_PAYLOAD=$(cat <<'EOF'
{
  "name": "epic-branches",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/epic/**"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "required_linear_history" }
  ]
}
EOF
)

if [ "${1:-}" = "epic-ruleset" ]; then
    shift
    EPIC_APPLY=0
    if [ "${1:-}" = "--apply" ]; then
        EPIC_APPLY=1
        shift
    fi
    if [ "$EPIC_APPLY" != "1" ]; then
        echo "$EPIC_RULESET_PAYLOAD"
        exit 0
    fi
    REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
    echo "==> Applying 'epic-branches' ruleset to epic/** on $REPO"
    EPIC_RULESET_ID=$(gh api "/repos/$REPO/rulesets" -q '.[] | select(.name=="epic-branches") | .id')
    if [ -n "$EPIC_RULESET_ID" ]; then
        echo "    (Updating existing ruleset ID: $EPIC_RULESET_ID)"
        gh api -X PUT "/repos/$REPO/rulesets/$EPIC_RULESET_ID" --input - <<< "$EPIC_RULESET_PAYLOAD" > /dev/null
    else
        echo "    (Creating new ruleset)"
        gh api -X POST "/repos/$REPO/rulesets" --input - <<< "$EPIC_RULESET_PAYLOAD" > /dev/null
    fi
    echo "Done. Nothing else was changed."
    exit 0
fi

# Get repository context
REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

echo "==> Securing repository: $REPO"

# 0. Ensure 'develop' branch exists and set as default
if ! gh api "/repos/$REPO/branches/develop" --silent 2>/dev/null; then
    echo "--> Creating 'develop' branch..."
    MASTER_SHA=$(gh api "/repos/$REPO/commits/master" -q .sha)
    gh api -X POST "/repos/$REPO/git/refs" -f ref="refs/heads/develop" -f sha="$MASTER_SHA" > /dev/null
fi

echo "--> Setting 'develop' as the default branch..."
gh repo edit "$REPO" --default-branch develop

# 1. Enable Basic GitHub Features
echo "--> Enabling vulnerability alerts and security fixes..."
gh api -X PUT "/repos/$REPO/vulnerability-alerts" > /dev/null
gh api -X PUT "/repos/$REPO/automated-security-fixes" > /dev/null

echo "--> Configuring repo settings (delete-branch-on-merge, secret scanning)..."
gh repo edit "$REPO" \
    --delete-branch-on-merge \
    --enable-secret-scanning \
    --enable-secret-scanning-push-protection

# 2. Legacy 'Branch Protection' ruleset (opt-in)
#
# WARNING: this payload is stale. The live repo is protected by two other
# rulesets, 'develop' and 'stable-branches', which this script does not manage.
# Applying this one adds a third ruleset on master + develop. It differs from
# the live rules: it requires signed commits on develop (rebase merges done by
# GitHub are unsigned, so they would be rejected) and it does not require a
# code-owner review. Do not apply it to a repo that already has the live
# rulesets. It only runs with APPLY_BRANCH_PROTECTION=1.
if [ "${APPLY_BRANCH_PROTECTION:-0}" = "1" ]; then
    echo "--> Applying 'Branch Protection' ruleset to master and develop..."
    RULESET_ID=$(gh api "/repos/$REPO/rulesets" -q '.[] | select(.name=="Branch Protection") | .id')

    # Note: We don't enforce specific status check names by default as they are dynamic (matrix)
    # but we do require that the overall CI pipeline passes.
    RULESET_PAYLOAD=$(cat <<EOF
{
  "name": "Branch Protection",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [
    {
      "actor_id": 5,
      "actor_type": "RepositoryRole",
      "bypass_mode": "pull_request"
    }
  ],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/master", "refs/heads/develop"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_signatures" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "required_review_thread_resolution": true
      }
    }
  ]
}
EOF
    )

    if [ -n "$RULESET_ID" ]; then
        echo "    (Updating existing ruleset ID: $RULESET_ID)"
        gh api -X PUT "/repos/$REPO/rulesets/$RULESET_ID" --input - <<< "$RULESET_PAYLOAD" > /dev/null
    else
        echo "    (Creating new ruleset)"
        gh api -X POST "/repos/$REPO/rulesets" --input - <<< "$RULESET_PAYLOAD" > /dev/null
    fi
    BRANCH_PROTECTION_STATE="APPLIED (legacy 'Branch Protection' ruleset on master/develop)"
else
    echo "--> Skipping the legacy 'Branch Protection' ruleset (set APPLY_BRANCH_PROTECTION=1 to apply; see the warning in this script)."
    BRANCH_PROTECTION_STATE="NOT CHANGED (existing rulesets left as they are)"
fi

echo "✓ Repository secured successfully!"
echo "Summary of protections applied:"
echo " - Default Branch: develop"
echo " - Stable/Release Branch: master"
echo " - Dependabot Security Updates: ENABLED"
echo " - Secret Scanning: ENABLED"
echo " - Push Protection: ENABLED"
echo " - Branch Rulesets: $BRANCH_PROTECTION_STATE"
echo " - Epic Branches Ruleset: not touched (use: scripts/secure-repo.sh epic-ruleset [--apply])"
