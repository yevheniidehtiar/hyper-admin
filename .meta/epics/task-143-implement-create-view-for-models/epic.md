---
type: epic
id: tT--3dT65NAO
title: "Task 1.4.3: Implement create view for models"
status: done
priority: medium
owner: null
labels:
  - frontend
  - jules
milestone_ref: null
github:
  issue_number: 85
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:cc6f4aa69c5bfe6008cd9edff3cce9f4248a09d01c49fa850ba2a7bc4b2e8265
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2025-09-10T18:37:22Z
updated_at: 2025-09-25T06:40:49Z
---

**Issue Title:** Task 1.4.3: Implement create view for models

**Agent Persona:** Frontend Agent

**Description**

Implement the create view for models, which will provide a form for creating new records. This view should leverage the established Jinja2 templating system and incorporate HTMX for dynamic form submission, validation feedback, and partial updates, ensuring a smooth user experience without full page reloads.

**Acceptance Criteria**

*   [ ] The form is correctly displayed with all fields.
*   [ ] Form submission via HTMX works correctly.
*   [ ] Various validation scenarios (e.g., valid data, invalid data, missing required fields) and ensure appropriate error messages are displayed.
*   [ ] Successful record creation and redirection to the detail view.
*   [ ] Unit tests are written and pass.
*   [ ] Playwright e2e tests are written.

**Additional Guidance for Agent**

1.  **Implementation Details & Technical Stack:**
    *   **Architecture & Patterns:** Leverage the existing Jinja2 templating system.
    *   **Technologies/Libraries:** HTMX
    *   **Existing Code/Components:**
        *   Utilize the `form_layout.html` template for the overall structure.
        *   Use reusable UI for rendering form fields, buttons, and displaying validation errors.
    *   **New Components:** Create missing component templates.

2.  **Core Requirements & Business Logic:**
    *   **Functionality:**
        *   Implement form submission using `hx-post` to the appropriate endpoint.
        *   Handle form validation errors by swapping in updated form fragments with error messages (using `hx-swap` and `hx-target`)
        *   On successful creation, consider redirecting to the detail view of the new record using HTMX's `hx-redirect` or similar mechanism.
    *   **Data Handling:** Display a form with all the fields for a given model.
    *   **Validation:**
        *   Implement server-side validation for all fields.
        *   Provide clear and user-friendly error messages for invalid input.

3.  **Error Handling:**
    *   Implement graceful error handling for cases where form submission fails due to server-side issues.

4.  **Testing Requirements**
    *   **Unit & Integration Tests:**
        *   Test that the form is correctly displayed with all fields.
        *   Verify that form submission via HTMX works correctly.
        *   Test various validation scenarios (e.g., valid data, invalid data, missing required fields) and ensure appropriate error messages are displayed.
        *   Test successful record creation and redirection to the detail view.
        *   Write unit tests and run them till they pass.
    *   **End-to-End (E2E) Tests:** Write playwright e2e tests, but never run them if you are Jules.
    *   **Manual Verification:** N/A
