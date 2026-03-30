# Agent 7: Scheduled Agent

| Property | Value |
|---|---|
| **Tier** | Utility (Scan) / Production (Analysis) |
| **Trigger** | Weekly cron schedule |
| **Purpose** | Proactive health monitoring of the library |
| **Est. Cost** | 5k - 15k tokens per weekly scan |

## Weekly Scans

### 1. Dependency Staleness

```yaml
- uses: actions/setup-python@v5
- run: |
    pip install pip-audit safety
    pip-audit --format=json > audit.json
    safety check --json > safety.json
```

Claude Sonnet creates issues for:

- Dependencies with known CVEs (priority: **high**)
- Dependencies > 2 major versions behind (priority: **medium**)
- Dependencies with abandoned upstream (priority: **low**, flag for replacement)

### 2. Compatibility Matrix Check

- Are we testing against the latest Python release?
- Has a new version been released that we should add to the matrix?
- Are any versions in our matrix approaching EOL?

### 3. Tech Debt Scan

```bash
# TODO/FIXME/HACK comment count
grep -rn "TODO\|FIXME\|HACK" src/ --include="*.py" | wc -l
# Cyclomatic complexity
radon cc src/ -n C -j  # functions with complexity C or worse
```

### 4. Community Health Report

- GitHub stars trend (up/down/flat)
- Issue velocity (opened vs closed per week)
- PR merge time (getting slower?)
- Download stats from PyPI
- Unanswered issues older than 14 days

### 5. Confidence-Gated Workload Entry

The Scheduled Agent does **not** auto-create tasks. Instead:

```
Scan finds issue
  → Agent assigns confidence score (0-100%)
  → Confidence > 80%: Draft issue with label "scheduled:auto"
  → Confidence 50-80%: Draft issue with label "scheduled:review-needed"
  → Confidence < 50%: Added to weekly summary for human, no issue created
```

The human reviews the weekly summary and promotes items to the workload queue.
