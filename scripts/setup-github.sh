#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"

echo "==> Setting up GitHub repository labels for Agentic Workflow in $REPO..."

# Orchestration Labels
gh label create "idea" --repo "$REPO" --color "D4C5F9" --description "Raw idea, needs research" || true
gh label create "researched" --repo "$REPO" --color "C2E0C6" --description "Deep Research complete, score > 85%" || true
gh label create "planned" --repo "$REPO" --color "BFD4F2" --description "Roadmap Planning complete, issues created" || true
gh label create "approved" --repo "$REPO" --color "0E8A16" --description "Human approved, ready for implementation" || true
gh label create "in-progress" --repo "$REPO" --color "FBCA04" --description "Dev agent working on it" || true
gh label create "review" --repo "$REPO" --color "E99695" --description "PR submitted, awaiting review" || true
gh label create "qa-passed" --repo "$REPO" --color "0E8A16" --description "All tests green, compat matrix clean" || true
gh label create "released" --repo "$REPO" --color "5319E7" --description "Shipped in a release" || true
gh label create "needs-human" --repo "$REPO" --color "D93F0B" --description "Agent escalation, human intervention needed" || true

# Work Queue Labels (used by conductor / run-autonomous-team)
gh label create "agent-task" --repo "$REPO" --color "D4C5F9" --description "Assigned to autonomous agent for implementation" || true
gh label create "ready"      --repo "$REPO" --color "0E8A16" --description "Issue unblocked and approved — ready for autonomous pickup" || true

# Sizing & Triage Labels
gh label create "size:S" --repo "$REPO" --color "C5DEF5" --description "1-2 hours effort" || true
gh label create "size:M" --repo "$REPO" --color "BFD4F2" --description "2-4 hours effort" || true
gh label create "size:L" --repo "$REPO" --color "A2C4EA" --description "4-8 hours effort" || true
gh label create "agent:jules" --repo "$REPO" --color "D4E5AE" --description "Assigned to Jules" || true
gh label create "agent:ai" --repo "$REPO" --color "F9D0C4" --description "Assigned to claude-sonnet-4-6" || true
gh label create "epic" --repo "$REPO" --color "7057FF" --description "Parent issue with sub-issues" || true
gh label create "community" --repo "$REPO" --color "BFDADC" --description "From external contributor" || true
gh label create "scheduled:auto" --repo "$REPO" --color "FEF2C0" --description "Created by scheduled agent (high confidence)" || true
gh label create "scheduled:review-needed" --repo "$REPO" --color "F9D0C4" --description "Needs human review" || true

# Merge Queue Labels (used by conductor / delivery-manager)
gh label create "merge-requested" --repo "$REPO" --color "FEF2C0" --description "PR approved + CI green, queued for conductor evaluation" || true
gh label create "merge-granted"   --repo "$REPO" --color "0E8A16" --description "Conductor approved merge — safe to merge, no conflict risk" || true
gh label create "merge-deferred"  --repo "$REPO" --color "D93F0B" --description "Conductor deferred merge — reason in PR comment" || true

echo "✓ GitHub labels configured for $REPO"

# Initialize Project Memory if gh command available
if [ -f ".github/project-memory.json" ]; then
    echo "✓ Project memory already exists"
else
    echo "==> Initializing .github/project-memory.json..."
    cat <<EOF > .github/project-memory.json
{
  "current_version": "0.1.0",
  "supported_versions": ["0.1.x"],
  "pending_deprecations": [],
  "roadmap": {
    "next_milestone": "v0.1.0",
    "planned_features": [],
    "tech_debt_items": 0
  },
  "agent_performance": {
    "jules_success_rate": 1.0,
    "avg_review_iterations": 1.0,
    "avg_task_completion_hours": 0.0
  },
  "community": {
    "contributors": 0,
    "open_issues": 0,
    "weekly_downloads": 0
  }
}
EOF
    echo "✓ Project memory initialized"
fi
