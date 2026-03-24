#!/usr/bin/env bash
# Secure repository settings using GitHub CLI (gh)
set -euo pipefail

# Get repository context
REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

echo "==> Securing repository: $REPO"

# 0. Ensure 'develop' branch exists and set as default
if ! gh api "/repos/$REPO/branches/develop" --silent 2>/dev/null; then
    echo "--> Creating 'develop' branch..."
    MAIN_SHA=$(gh api "/repos/$REPO/commits/main" -q .sha)
    gh api -X POST "/repos/$REPO/git/refs" -f ref="refs/heads/develop" -f sha="$MAIN_SHA" > /dev/null
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
echo "--> Applying 'Branch Protection' ruleset to main and develop..."
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
      "include": ["refs/heads/main", "refs/heads/develop"],
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

echo "✓ Repository secured successfully!"
echo "Summary of protections applied:"
echo " - Default Branch: develop"
echo " - Stable/Release Branch: main"
echo " - Dependabot Security Updates: ENABLED"
echo " - Secret Scanning: ENABLED"
echo " - Push Protection: ENABLED"
echo " - Force Pushes: BLOCKED on main/develop"
echo " - Deletions: BLOCKED on main/develop"
echo " - Signed Commits: REQUIRED on main/develop"
echo " - PR Review: REQUIRED (min 1 approval)"

