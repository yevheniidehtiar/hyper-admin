---
description: Run a full OSS triage audit — detect AI-slop, ego-PRs, duplicates, enforce lifecycle labels, close stale items
argument-hint: "[dry-run|live]"
---

Run the `oss-triage-auditor` agent to audit all open GitHub issues and PRs.

**Mode:** $ARGUMENTS (default: `dry-run`)

- `dry-run` — Collect all data, run all heuristics, produce the report. No GitHub state is mutated.
- `live` — Execute all mutations (label changes, closes, comments) and produce the report.

Steps:
1. Invoke the oss-triage-auditor agent with the specified mode
2. The agent fetches all open issues, PRs, milestones, and labels via `gh` CLI
3. It scores each item against AI-slop and ego-PR heuristics
4. It detects duplicate issues via title/body similarity
5. It enforces the label-based lifecycle state machine
6. It applies TTL rules to close stale items
7. It produces a structured markdown audit report

**Prerequisites:** Authenticated `gh` CLI with access to the repository.
