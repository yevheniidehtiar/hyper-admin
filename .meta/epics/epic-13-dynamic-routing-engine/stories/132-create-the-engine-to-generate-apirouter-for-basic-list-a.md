---
type: story
id: can0yseH9eTD
title: "1.3.2: Create the engine to generate APIRouter for basic list and detail/create views based on registered models."
status: done
priority: medium
assignee: yevheniidehtiar
labels:
  - backend
  - task
  - routing
  - fastapi
  - in-progress
estimate: null
epic_ref:
  id: o-eJ-cPOunsK
github:
  issue_number: 28
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:f2ed67de1b51728f2c35f674aa8444fae6fdedf4bd11149bf8522c812f7e647f
  synced_at: 2026-04-07T17:23:23.789Z
created_at: 2025-08-24T20:06:07Z
updated_at: 2025-09-12T20:16:26Z
---


**Task ID:** 1.3.2
**Epic:** Epic 1.3: Dynamic Routing Engine
**Phase:** Phase 1: MVP Foundation
**Assigned Agent Profile:** Backend Agent

**Goal:**

The goal of this task is to create the engine that generates an `APIRouter` for basic list, detail, create, and update views, rendering HTML templates for seamless integration with HTMX, based on the models registered with the HyperAdmin site.

**Description:**

This task builds upon the `hyperadmin.routing` module created in the previous task (1.3.1). It involves creating the engine that will generate the `APIRouter` for the registered models. This includes:

1.  **`APIRouter` Generation:** A function or class that takes the registered models and generates an `APIRouter` with the appropriate HTML-rendering endpoints.
2.  **View Function Integration:** The generated routes should be connected to the basic view functions for list, detail, create, and update operations, ensuring they render appropriate HTML templates for HTMX.
3.  **URL Path Generation:** The URL paths for the generated routes should be based on the model's name and follow RESTful conventions.

## Additional Guidance for Agent:

### Authentication and Authorization:
For the initial implementation of this module, you can assume that endpoints are public. However, it's crucial to acknowledge that authentication and authorization will be a mandatory subsequent phase for a secure admin interface.

### Error Handling:
For error handling, please use `fastapi.HTTPException`.

### Testing:
Please strive for 99% test coverage for this module, as per the `GEMINI.md` guidelines. Focus on scenarios such as:
*   Correct generation of `APIRouter` instances for various registered models.
*   Proper integration of view functions that render HTML templates.
*   Accurate URL path generation.
*   Robust error handling for cases like invalid model registrations.
*   Ensure the generated `APIRouter` can be successfully included in a FastAPI application.

**Acceptance Criteria:**

*   An engine is created that can generate an `APIRouter` for the registered models.
*   The generated `APIRouter` includes HTML-rendering endpoints for list, detail, create, and update operations.
*   The URL paths for the generated routes are correctly formatted.
*   The generated `APIRouter` can be successfully included in a FastAPI application.
*   The implementation is well-tested and includes documentation.
