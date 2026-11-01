---
type: story
id: 5KAGnNK84hEY
title: "chore(plugin-tasks): scaffold plugins/hyperadmin-tasks workspace package"
status: done
priority: high
assignee: null
labels:
  - agent-task
  - size:S
  - planned
  - plugin
estimate: null
epic_ref:
  id: M437OCoW6YMr
github:
  issue_number: 740
  repo: yevheniidehtiar/hyper-admin
  synced_at: 2026-11-01T00:00:00Z
created_at: 2026-10-29T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Context

Create the package skeleton modelled on `plugins/hyperadmin-reports/` so later stories only add modules.

**Spec:** [`docs/specs/plugin-tasks.md`](../../../../docs/specs/plugin-tasks.md)

## Scenarios

**Scenario: plugin registers seams**
  Given the package is a uv workspace member
  When  Admin is constructed with plugins enabled
  Then  the /tasks page, the "Tasks" nav section and view_tasks/manage_tasks permissions are registered

**Scenario: plugin can be disabled**
  Given hyperadmin-tasks is installed
  When  Admin is constructed with disabled_plugins=["tasks"]
  Then  no /tasks route and no Tasks nav entry exist

## Acceptance Criteria

- [ ] `pyproject.toml` with entry point `tasks = "hyperadmin_tasks.plugin:TasksPlugin"`, `requires-python >=3.11`, `hyper-admin = {workspace = true}`
- [ ] Root `[tool.uv.workspace]` already globs `plugins/*`; add to dev group like hyperadmin-reports
- [ ] `TasksPlugin.on_register` adds template dir, placeholder page, nav section, two permissions
- [ ] Unit tests for both scenarios

## Files Likely Affected

- `plugins/hyperadmin-tasks/pyproject.toml`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/__init__.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/plugin.py`
- `plugins/hyperadmin-tasks/src/hyperadmin_tasks/routes.py`
- `plugins/hyperadmin-tasks/tests/test_plugin.py`
- `pyproject.toml`

## Dependencies

Depends on: `reviewspec-approve-sdd-for-plugin-tasks`

## Notes for Implementer

Mirror `plugins/hyperadmin-reports/src/hyperadmin_reports/plugin.py`. Dependency change to root pyproject ships in its own commit (CONSTITUTION §7).
