---
type: epic
id: ep-rh-01
title: "epic(core): record history timeline with field diffs"
status: backlog
priority: medium
owner: null
labels:
  - planned
  - area:core
  - backend
  - frontend
  - size:L
created_at: 2026-11-01T00:00:00Z
updated_at: 2026-11-01T00:00:00Z
---

## Overview

Who changed what and when: a history tab on the detail page listing create, update and
delete events with the user, the time and a field-by-field diff, with sensitive fields
redacted. Admins rely on it for support, debugging and compliance (Django admin history,
Directus revisions, Payload versions and Nova's action log all offer it).

Size L and touches `core/`, `views/` and the adapters, so it needs its own SDD first
(`st-rh-00`). It must share one log with the audit trail planned in
`epic-v057-permissions-matrix`. No milestone yet; the owner picks one when the SDD is approved.

## Stories (bottom-up)

| ID | Story | Size | Blocked by |
|---|---|---|---|
| st-rh-00 | [docs(spec): write and approve the record history SDD](stories/docsspec-write-and-approve-the-record-history-sdd.md) | S | — |
