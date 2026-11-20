---
type: epic
id: ep-v100-freeze-01
title: "epic(release): v1.0 API freeze — public API audit, versioning policy, migration guides, docs"
status: todo
priority: high
owner: null
labels:
  - planned
  - area:docs
  - area:core
milestone_ref:
  id: v100-release-01
created_at: 2026-11-20T00:00:00Z
updated_at: 2026-11-20T00:00:00Z
---

## Overview

The part of v1.0 — Stable Release that does not need the PyPI alpha: the stability commitment and the docs
that go with it. The release itself and dogfood-1 stay in `epic-v100-go-live` and are the owner's call.

Each story maps to one bullet of `.meta/roadmap/milestones/v100-stable-release.md`:

- `st-v100-freeze-01`: versioning and deprecation policy.
- `st-v100-freeze-02`: migration guides from Django admin, SQLAdmin and Flask-Admin (RFC #274).
- `st-v100-freeze-03`: public API audit, every export documented, typed and covered, with a drift guard.
- `st-v100-freeze-04`: docs site complete, tutorial, existing-app guide, reference, recipes.

No SDD: the stories are docs and tests, and none of them changes behaviour.

## Order

`-01` and `-02` are independent. `-03` runs after the feature epics still open on 2026-11-20 have merged
(OAuth SSO, dashboard builder, plugin registry hooks, hyperadmin-logfire), so the audit sees the final
exports. `-04` runs last and links what the others published.
