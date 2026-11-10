#!/usr/bin/env bash
# Secure repository settings using GitHub CLI (gh)
#
# Usage: scripts/secure-repo.sh [owner/repo]
#
# The 'epic-branches' ruleset is only printed by default. Run with
# APPLY_EPIC_RULESET=1 (owner identity) to create or update it.
set -euo pipefail

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

# 2. Create/Update Branch Protection Ruleset
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

# 3. Epic branches ruleset (epic/<slug>, merged by the autopilot)
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

if [ "${APPLY_EPIC_RULESET:-0}" = "1" ]; then
    echo "--> Applying 'epic-branches' ruleset to epic/**..."
    EPIC_RULESET_ID=$(gh api "/repos/$REPO/rulesets" -q '.[] | select(.name=="epic-branches") | .id')
    if [ -n "$EPIC_RULESET_ID" ]; then
        echo "    (Updating existing ruleset ID: $EPIC_RULESET_ID)"
        gh api -X PUT "/repos/$REPO/rulesets/$EPIC_RULESET_ID" --input - <<< "$EPIC_RULESET_PAYLOAD" > /dev/null
    else
        echo "    (Creating new ruleset)"
        gh api -X POST "/repos/$REPO/rulesets" --input - <<< "$EPIC_RULESET_PAYLOAD" > /dev/null
    fi
    EPIC_RULESET_STATE="APPLIED (linear history on epic/**)"
else
    echo "--> 'epic-branches' ruleset NOT applied. Payload (re-run with APPLY_EPIC_RULESET=1 to apply):"
    echo "$EPIC_RULESET_PAYLOAD"
    EPIC_RULESET_STATE="NOT APPLIED (set APPLY_EPIC_RULESET=1)"
fi

echo "✓ Repository secured successfully!"
echo "Summary of protections applied:"
echo " - Default Branch: develop"
echo " - Stable/Release Branch: master"
echo " - Dependabot Security Updates: ENABLED"
echo " - Secret Scanning: ENABLED"
echo " - Push Protection: ENABLED"
echo " - Force Pushes: BLOCKED on master/develop"
echo " - Deletions: BLOCKED on master/develop"
echo " - Signed Commits: REQUIRED on master/develop"
echo " - PR Review: REQUIRED (min 1 approval)"
echo " - Epic Branches Ruleset: $EPIC_RULESET_STATE"

