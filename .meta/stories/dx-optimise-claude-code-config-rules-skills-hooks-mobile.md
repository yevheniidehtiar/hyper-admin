---
type: story
id: WAaDFI_r7CHZ
title: "dx: optimise Claude Code config — rules, skills, hooks, mobile"
status: done
priority: medium
assignee: null
labels: []
estimate: null
epic_ref: null
github:
  issue_number: 134
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:9e2d98fc7dc6cc9fc81b97473c9501b60921e7e356722df6401302d37c245148
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-17T23:57:51Z
updated_at: 2026-03-19T19:22:03Z
---

## Summary

Implement Claude Code best practices to improve developer experience and agentic workflow efficiency.

## Changes

- **Split `CLAUDE.md`** into `.claude/rules/` with path-scoped files (code-style, testing) — keeps main file under 200 lines for token savings
- **`.claude/settings.json`** — shared hook: auto-format Python files with ruff after Edit/Write
- **`.claude/settings.local.json`** — personal hook: macOS notification on permission prompts (mobile-friendly)
- **`.claude/skills/fix-issue/SKILL.md`** — slash command to implement a GitHub issue end-to-end (TDD, branch, PR)

## Motivation

- Reduce token consumption on Claude Pro by scoping rules to relevant file paths
- Enable unattended/mobile workflows via desktop notifications
- Standardise issue-driven development with a reusable `/fix-issue` skill
