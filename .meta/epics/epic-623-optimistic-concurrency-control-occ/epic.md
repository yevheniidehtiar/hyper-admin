---
type: epic
id: UxLOg-H5WxzR
title: "Epic 6.2.3: Optimistic Concurrency Control (OCC)"
status: todo
priority: medium
owner: null
labels:
  - agent-task
  - area:concurrency
milestone_ref:
  id: EnCx0HBhFy40
github:
  issue_number: 332
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0827df042c26c7685838becc4af3ea039e2a9f8347f5bad3e2821dfda7c6cef2
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-29T07:02:28Z
updated_at: 2026-03-29T07:02:28Z
---

## Overview
Prevents lost updates when two admins edit the same record simultaneously. Implements version field detection, StaleRecordError, adapter-level OCC enforcement, view-layer conflict handling (HTTP 409), and conflict dialog UI.

## Roadmap Reference
Epic 6.2.3 — Optimistic Concurrency Control (OCC)

## Milestone
v0.6.2

## Tasks
- [ ] #314 — test(concurrency): version_field detection + StaleRecordError unit tests
- [ ] #315 — feat(concurrency): core/concurrency.py — version detection + StaleRecordError
- [ ] #316 — test(concurrency): BaseAdapter.update() with expected_version parameter
- [ ] #317 — feat(concurrency): OCC in BaseAdapter + SQLModelAdapter + SQLAlchemyAdapter
- [ ] #318 — test(concurrency): update_view OCC handling — hidden __version field + 409 response
- [ ] #319 — feat(concurrency): OCC wiring in update_form_view + update_view
- [ ] #320 — feat(concurrency): conflict_dialog.html component
- [ ] #321 — test(e2e): OCC conflict detection — two sessions editing same record

## Parallel Tracks
This entire epic (Track B) is INDEPENDENT of Epic 6.2.1 and 6.2.2 (Track A) and can be developed in parallel.
