---
type: epic
id: fAZXHu4TtVlv
title: "epic: Engine & Connection Management (pool tuning, rate limiting)"
status: todo
priority: medium
owner: null
labels:
  - area:core
  - performance
milestone_ref:
  id: r5QTaoU0QKpG
github:
  issue_number: 212
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:69b771c932a870ca9e2819798df27393c85834d755cc861680d6282f5760c7ad
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2026-03-27T00:38:07Z
updated_at: 2026-03-27T00:46:40Z
---

## Overview
Parent epic for engine configuration and request-level protection.

## Sub-issues

### B1: Configurable engine kwargs
- #231 test: unit tests for engine factory
- #232 feat(core): engine factory accepting pool configuration

### B2: Rate limiting middleware
- #233 test: unit tests for rate limiting middleware
- #234 feat(core): rate limiter protocol and in-memory implementation
- #235 feat(views): RateLimitMiddleware using core protocol

## Bottlenecks addressed
- Default connection pool (size=5, overflow=10) can't sustain 100 req/s
- No rate limiting — spike traffic directly hits DB
