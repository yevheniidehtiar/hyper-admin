---
type: epic
id: -oIxBQIQA8WM
title: "epic: add --quiet flag to CLI example app to suppress startup banner"
status: done
priority: medium
owner: null
labels:
  - agent-task
milestone_ref: null
github:
  issue_number: 287
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:1cef3d2d7b1f2b2635d46c76f0b6f484104f883c33215fd8f0ac12a1de1c708e
  synced_at: 2026-04-07T17:23:23.791Z
created_at: 2026-03-27T23:06:54Z
updated_at: 2026-03-27T23:23:51Z
---

## Overview
Add a `--quiet` flag to the HyperAdmin CLI and example apps that suppresses startup banner output
when launching the admin interface. Implements bottom-up: core model first, then CLI wiring,
then example app updates, and finally test coverage.

## Tasks
- [ ] #283 feat(core): add show_banner parameter to Admin class
- [ ] #284 feat(cli): add --quiet flag to Typer CLI entry point
- [ ] #285 feat(examples): wire --quiet flag into simple and erp example apps
- [ ] #286 test: unit tests for Admin show_banner and CLI --quiet flag
