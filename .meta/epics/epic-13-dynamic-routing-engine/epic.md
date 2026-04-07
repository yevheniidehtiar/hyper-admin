---
type: epic
id: o-eJ-cPOunsK
title: "Epic 1.3: Dynamic Routing Engine"
status: done
priority: medium
owner: yevheniidehtiar
labels:
  - backend
  - routing
  - fastapi
  - in-progress
milestone_ref:
  id: R0snJmL9dKU-
github:
  issue_number: 18
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:94f563503fb81541e06731fe67f439edf06c5926ae6e401ac0df99ebbaf3f019
  synced_at: 2026-04-07T17:23:23.789Z
created_at: 2025-08-23T13:55:01Z
updated_at: 2025-09-12T20:16:40Z
---


This epic focuses on implementing a dynamic routing engine that automatically generates FastAPI endpoints that render HTML templates for seamless integration with HTMX, based on registered models. It provides the foundation for the admin interface's dynamic UI.

**User Story:**

As a developer using HyperAdmin, I want the admin interface to automatically generate HTML-rendering endpoints for my registered models, so that I can quickly have a functional admin interface without manually defining routes for each model, leveraging HTMX for dynamic interactions.

**Acceptance Criteria:**

*   A routing module is created that can dynamically generate FastAPI endpoints rendering HTML.
*   The generated HTML-rendering endpoints seamlessly integrate with the registered models.
*   Basic list and detail/create views are functional, serving HTML for HTMX.
*   The routing system is extensible to support additional view types in the future.
*   All generated endpoints follow appropriate web conventions for HTML rendering.
*   The system is well-tested to ensure reliability and correctness.

## Tasks:
- [x] #27
- [x] #28
