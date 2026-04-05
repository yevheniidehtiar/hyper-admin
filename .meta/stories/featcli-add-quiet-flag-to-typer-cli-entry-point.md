---
type: story
id: FBfHSdPaP0K6
title: "feat(cli): add --quiet flag to Typer CLI entry point"
status: done
priority: medium
assignee: null
labels:
  - enhancement
  - agent-task
  - size:XL
estimate: null
epic_ref: null
github:
  issue_number: 284
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:db6ec4cc16f7c9e882739abc4dcb73459312520e9040df1ea797fe75bd25a49c
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T23:06:05Z
updated_at: 2026-03-27T23:36:27Z
---

## Context
The HyperAdmin management CLI (`src/hyperadmin/__main__.py`) uses Typer. Adding a `--quiet` flag
at the CLI level allows users to suppress the startup banner output when launching the admin server
from the command line (e.g. `python -m hyperadmin serve --quiet`).

## Acceptance Criteria
- [ ] A `--quiet / --no-quiet` option is added to the relevant Typer command
- [ ] When `--quiet` is passed, `show_banner=False` is forwarded to the `Admin` constructor
- [ ] When `--quiet` is omitted, default behavior (`show_banner=True`) is preserved
- [ ] Help text for `--quiet` reads: "Suppress startup banner output"
- [ ] Type hints and mypy compliance verified

## Files Likely Affected
- `src/hyperadmin/__main__.py`
- `src/hyperadmin/management/commands/` (whichever command runs the server)

## Dependencies
Depends on: #283

## Notes for Implementer
- Use Typer's `typer.Option(False, "--quiet/--no-quiet", help="Suppress startup banner output")`
- Do not introduce a new top-level command if a serve/run command already exists — extend it
- Follow CONSTITUTION.md §1: CLI wiring lives in management commands, not in core/
