---
description: Create GitHub issues from an implementation plan for agent-driven development
argument-hint: "<feature or fix request>"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Agent
---

@.claude/project-config.md

You are a planning agent. Your job is to analyze the request, produce an implementation plan,
and create one GitHub issue per plan step. Do NOT implement anything yourself.

At the start of every run, derive the repo context:

```bash
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
```

## Request

$ARGUMENTS

## Instructions

### 1. Analyze

- Read CONSTITUTION.md, ROADMAP.md, .claude/rules/planning-playbook.md, and any files relevant to the request
- Break the request into discrete, independently implementable tasks
- Order tasks strictly by dependency and architectural layer (Architecture/Models -> Business Logic -> View/Middleware -> UI), following the Planning Playbook.

### 2. Size each task

Assign a size label based on complexity:
- `size:small` — single file, < 50 lines changed, straightforward (good for fix-issue skill)
- `size:medium` — 2-4 files, moderate logic, may need tests
- `size:large` — cross-cutting, architectural, or needs deep context (Claude-level)

### 3. Determine issue type

Use Conventional Commit types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

### 4. Create a tracking issue

Create a parent issue that lists all child tasks as a checklist:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue create \
  --title "epic: $SHORT_DESCRIPTION" \
  --label "epic,agent-task" \
  --body "$(cat <<'BODY'
## Overview
<brief description of the overall goal>

## Tasks
- [ ] #<child-1>
- [ ] #<child-2>
...
BODY
)"
```

### 5. Create child issues

For each task, create an issue:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue create \
  --title "type(scope): description" \
  --label "agent-task,size:SIZE,TYPE_LABEL" \
  --body "$(cat <<'BODY'
## Context
<why this task exists, what it enables>

## Acceptance Criteria
- [ ] criterion 1
- [ ] criterion 2

## Files Likely Affected
- `path/to/file.py`

## Dependencies
Depends on: #N (if any)

## Notes for Implementer
<relevant CONSTITUTION.md rules, patterns to follow, edge cases>
BODY
)"
```

Map type to existing labels: `feat` → `enhancement`, `fix` → `bug`, `docs` → `documentation`.
For types without existing labels (`refactor`, `test`, `chore`, `perf`), use only `agent-task` + size.

### 5.5 Add issues to GitHub Project

After all child issues are created, add them to a GitHub ProjectV2 so the team can track
progress, planning, and timeline visually. Milestones and epics appear on the roadmap timeline.

All mutations use `GH_TOKEN="$CLAUDE_GH_TOKEN"` and the runtime-derived `$OWNER`/`$REPO_NAME`.

#### 5.5a — Find or create the project

```bash
# Get the owner's node ID (required for createProjectV2)
OWNER_ID=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql -f query='
  query { viewer { id } }
' --jq '.data.viewer.id')

# Look for an existing project with the HyperAdmin: prefix
EXISTING_PROJECT=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='query($login: String!) {
    user(login: $login) {
      projectsV2(first: 20) { nodes { id title number url } }
    }
  }' \
  -f login="$OWNER" \
  --jq ".data.user.projectsV2.nodes[] | select(.title | startswith(\"${PROJECT_NAME_PREFIX}\")) | first")

if [ -z "$EXISTING_PROJECT" ]; then
  PROJECT_TITLE="${PROJECT_NAME_PREFIX} ${MILESTONE_TITLE}"
  RESULT=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
    -f query='mutation($ownerId: ID!, $title: String!) {
      createProjectV2(input: {ownerId: $ownerId, title: $title}) {
        projectV2 { id number url }
      }
    }' \
    -f ownerId="$OWNER_ID" -f title="$PROJECT_TITLE")
  PROJECT_ID=$(echo "$RESULT" | jq -r '.data.createProjectV2.projectV2.id')
  PROJECT_URL=$(echo "$RESULT" | jq -r '.data.createProjectV2.projectV2.url')
else
  PROJECT_ID=$(echo "$EXISTING_PROJECT" | jq -r '.id')
  PROJECT_URL=$(echo "$EXISTING_PROJECT" | jq -r '.url')
fi
```

#### 5.5b — Ensure custom fields exist

Query existing fields first; create only missing ones to stay idempotent.

```bash
FIELDS=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='query($projectId: ID!) {
    node(id: $projectId) {
      ... on ProjectV2 {
        fields(first: 20) {
          nodes {
            ... on ProjectV2Field { id name }
            ... on ProjectV2SingleSelectField { id name options { id name } }
          }
        }
      }
    }
  }' -f projectId="$PROJECT_ID")

# Create Status field if missing
if ! echo "$FIELDS" | jq -e '.data.node.fields.nodes[] | select(.name=="Status")' > /dev/null; then
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql -f query='
    mutation($pid: ID!) {
      createProjectV2Field(input: {
        projectId: $pid, dataType: SINGLE_SELECT, name: "Status",
        singleSelectOptions: [
          {name:"Backlog",   color:GRAY,   description:"Not yet started"},
          {name:"Ready",     color:BLUE,   description:"Ready for implementation"},
          {name:"In Progress",color:YELLOW,description:"Being worked on"},
          {name:"Review",    color:ORANGE, description:"PR open, awaiting review"},
          {name:"Done",      color:GREEN,  description:"Merged and complete"}
        ]
      }) { projectV2Field { id } }
    }' -f pid="$PROJECT_ID"
fi

# Create Size field if missing
if ! echo "$FIELDS" | jq -e '.data.node.fields.nodes[] | select(.name=="Size")' > /dev/null; then
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql -f query='
    mutation($pid: ID!) {
      createProjectV2Field(input: {
        projectId: $pid, dataType: SINGLE_SELECT, name: "Size",
        singleSelectOptions: [
          {name:"S",color:BLUE,  description:"1-2 hours"},
          {name:"M",color:PURPLE,description:"2-4 hours"},
          {name:"L",color:RED,   description:"4-8 hours"}
        ]
      }) { projectV2Field { id } }
    }' -f pid="$PROJECT_ID"
fi

# Create Agent Tier field if missing
if ! echo "$FIELDS" | jq -e '.data.node.fields.nodes[] | select(.name=="Agent Tier")' > /dev/null; then
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql -f query='
    mutation($pid: ID!) {
      createProjectV2Field(input: {
        projectId: $pid, dataType: SINGLE_SELECT, name: "Agent Tier",
        singleSelectOptions: [
          {name:"Claude Code",color:PINK, description:"implement-feature skill"},
          {name:"Haiku",      color:GRAY, description:"delivery-manager / reviewer"},
          {name:"Sonnet",     color:BLUE, description:"conductor / complex tasks"}
        ]
      }) { projectV2Field { id } }
    }' -f pid="$PROJECT_ID"
fi

# Create date fields if missing
for FNAME in "Start Date" "End Date"; do
  if ! echo "$FIELDS" | jq -e ".data.node.fields.nodes[] | select(.name==\"$FNAME\")" > /dev/null; then
    GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
      -f query='mutation($pid: ID!, $name: String!) {
        createProjectV2Field(input: {projectId: $pid, dataType: DATE, name: $name}) {
          projectV2Field { id }
        }
      }' -f pid="$PROJECT_ID" -f name="$FNAME"
  fi
done

# Re-query fields to get all IDs and option IDs for use below
FIELDS=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='query($projectId: ID!) {
    node(id: $projectId) {
      ... on ProjectV2 {
        fields(first: 20) {
          nodes {
            ... on ProjectV2Field { id name }
            ... on ProjectV2SingleSelectField { id name options { id name } }
          }
        }
      }
    }
  }' -f projectId="$PROJECT_ID")

STATUS_FIELD_ID=$(echo "$FIELDS" | jq -r '.data.node.fields.nodes[] | select(.name=="Status") | .id')
STATUS_BACKLOG_ID=$(echo "$FIELDS" | jq -r '.data.node.fields.nodes[] | select(.name=="Status") | .options[] | select(.name=="Backlog") | .id')
SIZE_FIELD_ID=$(echo "$FIELDS" | jq -r '.data.node.fields.nodes[] | select(.name=="Size") | .id')
START_FIELD_ID=$(echo "$FIELDS" | jq -r '.data.node.fields.nodes[] | select(.name=="Start Date") | .id')
END_FIELD_ID=$(echo "$FIELDS" | jq -r '.data.node.fields.nodes[] | select(.name=="End Date") | .id')
TODAY=$(date +%Y-%m-%d)
```

#### 5.5c — Add each issue to the project and set field values

For every issue created in steps 4 and 5 (epic + all children), run this block:

```bash
# $ISSUE_NUMBER and $TASK_SIZE (S/M/L) must be set per issue

ISSUE_NODE_ID=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) { issue(number: $number) { id } }
  }' \
  -f owner="$OWNER" -f repo="$REPO_NAME" -F number="$ISSUE_NUMBER" \
  --jq '.data.repository.issue.id')

ITEM_ID=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='mutation($pid: ID!, $cid: ID!) {
    addProjectV2ItemById(input: {projectId: $pid, contentId: $cid}) {
      item { id }
    }
  }' -f pid="$PROJECT_ID" -f cid="$ISSUE_NODE_ID" \
  --jq '.data.addProjectV2ItemById.item.id')

# Set Status = Backlog
GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='mutation($pid: ID!, $iid: ID!, $fid: ID!, $oid: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $pid, itemId: $iid, fieldId: $fid,
      value: {singleSelectOptionId: $oid}
    }) { projectV2Item { id } }
  }' -f pid="$PROJECT_ID" -f iid="$ITEM_ID" \
     -f fid="$STATUS_FIELD_ID" -f oid="$STATUS_BACKLOG_ID"

# Set Size from task label
SIZE_OPT_ID=$(echo "$FIELDS" | jq -r \
  ".data.node.fields.nodes[] | select(.name==\"Size\") | .options[] | select(.name==\"$TASK_SIZE\") | .id")
GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
  -f query='mutation($pid: ID!, $iid: ID!, $fid: ID!, $oid: String!) {
    updateProjectV2ItemFieldValue(input: {
      projectId: $pid, itemId: $iid, fieldId: $fid,
      value: {singleSelectOptionId: $oid}
    }) { projectV2Item { id } }
  }' -f pid="$PROJECT_ID" -f iid="$ITEM_ID" \
     -f fid="$SIZE_FIELD_ID" -f oid="$SIZE_OPT_ID"

# For epics only: set Start Date = today
if [ "$IS_EPIC" = "true" ]; then
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
    -f query='mutation($pid: ID!, $iid: ID!, $fid: ID!, $date: Date!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $pid, itemId: $iid, fieldId: $fid, value: {date: $date}
      }) { projectV2Item { id } }
    }' -f pid="$PROJECT_ID" -f iid="$ITEM_ID" \
       -f fid="$START_FIELD_ID" -f date="$TODAY"
fi
```

#### 5.5d — Create project views (idempotent)

```bash
for VIEW in "Kanban:BOARD_LAYOUT" "Roadmap:ROADMAP_LAYOUT" "Table:TABLE_LAYOUT"; do
  VNAME=$(echo "$VIEW" | cut -d: -f1)
  VLAYOUT=$(echo "$VIEW" | cut -d: -f2)
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh api graphql \
    -f query='mutation($pid: ID!, $name: String!, $layout: ProjectV2ViewLayout!) {
      createProjectV2View(input: {projectId: $pid, name: $name, layout: $layout}) {
        projectV2View { id name }
      }
    }' -f pid="$PROJECT_ID" -f name="$VNAME" -f layout="$VLAYOUT" 2>/dev/null || true
done
```

> **Roadmap date binding**: After creation, open the Roadmap view in GitHub UI → view settings
> → set "Start date" to **Start Date** field and "End date" to **End Date** field.
> The GraphQL API does not yet expose view date-field binding.

### 6. Update tracking issue

After all child issues are created, edit the tracking issue body to include the actual issue numbers.

### 7. Output summary

Print a markdown table:

```
| # | Title | Size | Type | Depends On |
|---|-------|------|------|------------|
| 42 | feat(auth): add login endpoint | small | feat | — |
| 43 | test(auth): add login tests | small | test | #42 |
```

End with: "Created N issues. Tracking issue: #T. GitHub Project: $PROJECT_URL"
