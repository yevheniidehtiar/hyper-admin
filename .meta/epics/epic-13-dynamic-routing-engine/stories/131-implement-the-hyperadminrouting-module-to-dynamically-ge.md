---
type: story
id: -tmVccLGZ5sA
title: "1.3.1: Implement the hyperadmin.routing module to dynamically generate FastAPI endpoints."
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
  issue_number: 27
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:8973901ac6d70628ce58e917d99be724cb8a4a2a9e700eca331d224da2beebf7
  synced_at: 2026-04-07T17:23:23.789Z
created_at: 2025-08-24T20:05:42Z
updated_at: 2025-09-10T20:12:56Z
---


**Task ID:** 1.3.1
**Epic:** Epic 1.3: Dynamic Routing Engine
**Phase:** Phase 1: MVP Foundation
**Assigned Agent Profile:** Backend Agent

**Goal:**

The goal of this task is to implement the `hyperadmin.routing` module, which will be responsible for dynamically generating FastAPI endpoints that render HTML templates for seamless integration with HTMX, based on the models registered with the HyperAdmin site.

**Description:**

This task involves creating the core components of the routing system. This includes:

1.  **`APIRouter` class:** A class that will be used to create and manage the FastAPI router.
2.  **Route Generation Logic:** Logic that iterates through the registered models and generates the appropriate HTML-rendering endpoints for each model.
3.  **View Functions:** Basic view functions for list, detail, create, and update operations, which will render HTML templates.

**Important Clarification:**
These endpoints are designed to serve HTML content for HTMX-driven interactions. A separate, independent epic would be created if a pure JSON-based RESTful API is required for other purposes.

**Acceptance Criteria:**

*   The `hyperadmin.routing` module is created.
*   The module contains a class for generating FastAPI routers.
*   The router generation logic can correctly identify registered models.
*   Basic view functions are implemented for CRUD operations, rendering appropriate HTML templates.
*   The generated routes are correctly added to the FastAPI application.
*   The implementation is well-documented and includes type hints.

## Additional Guidance for Agent:

### Authentication and Authorization:
For the initial implementation of the routing module, you can assume that endpoints are public. However, it's crucial to acknowledge that authentication and authorization will be a mandatory subsequent phase for a secure admin interface.

### Error Handling:
For error handling, please use `fastapi.HTTPException`.

### Testing:
Please strive for 99% test coverage for the new routing module, as per the `GEMINI.md` guidelines. Focus on scenarios such as:
*   Correct generation of API endpoints for various registered models.
*   Proper handling of different HTTP methods (GET, POST, PUT, DELETE).
*   Accurate parsing and validation of request parameters.
*   Robust error handling for cases like non-existent resources or invalid input.
*   Ensure seamless integration with the `site.register` method, as this is crucial for dynamic endpoint generation.
