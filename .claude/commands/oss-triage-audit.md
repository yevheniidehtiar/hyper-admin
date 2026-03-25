---
description: Run a full OSS triage audit — detect AI-slop, ego-PRs, duplicates, enforce lifecycle labels, close stale items
argument-hint: "[dry-run|live] [--repo owner/repo]"
---

Run the OSS triage audit script:

```bash
uv run scripts/triage_audit.py $ARGUMENTS
```

If no arguments provided, defaults to `dry-run` against the current repo.

The script handles all 7 audit phases:
1. Data collection (issues, PRs, milestones, labels)
2. AI-slop scoring (description-to-code ratio, boilerplate, LLM markers)
3. Ego-PR scoring (whitespace-only, typo fixes, no linked issue)
4. Duplicate detection (Jaccard similarity, competing PRs)
5. Lifecycle enforcement (label state machine)
6. TTL / staleness checks (14d, 21d, 30d thresholds)
7. Markdown report output

**Prerequisites:** Authenticated `gh` CLI with access to the target repository.
