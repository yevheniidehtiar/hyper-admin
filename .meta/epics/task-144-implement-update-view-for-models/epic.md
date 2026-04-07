---
type: epic
id: h790OIFo40LW
title: "Task 1.4.4: Implement update view for models"
status: done
priority: medium
owner: null
labels:
  - frontend
milestone_ref: null
github:
  issue_number: 83
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:6aca994b353357592857e5563f20e55f9c89163c5911fa2ebd7cee4e0f35742a
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2025-09-10T18:20:55Z
updated_at: 2026-03-17T21:57:38Z
---

**Issue Title:** Task 1.4.4: Implement update view for models

**Agent Persona:** Frontend Agent

**Description**

Implement the update view for models, which will provide a form for updating existing records. This view should leverage the established Jinja2 templating system and incorporate HTMX for dynamic form submission, validation feedback, and partial updates, ensuring a smooth user experience without full page reloads.

**Acceptance Criteria**

*   [ ] The form is correctly pre-filled with existing data.
*   [ ] Form submission via HTMX works correctly.
*   [ ] Various validation scenarios [e.g., valid data, invalid data, missing required fields] and ensure appropriate error messages are displayed.
*   [ ] Successful update and redirection to the detail view.
*   [ ] Edge cases, such as attempting to update a non-existent record are handled.

**Additional Guidance for Agent**

1.  **Implementation Details & Technical Stack:**
    *   **Architecture & Patterns:** Leverage the existing Jinja2 templating system.
    *   **Technologies/Libraries:** HTMX
    *   **Existing Code/Components:**
        *   Utilize the `form_layout.html` template [from 1.4.1.2] for the overall structure.
        *   Use reusable UI components [from 1.4.1.3] for rendering form fields, buttons, and displaying validation errors.
    *   **New Components:** N/A

2.  **Core Requirements & Business Logic:**
    *   **Functionality:**
        *   Implement form submission using `hx-post` to the appropriate endpoint.
        *   Handle form validation errors by swapping in updated form fragments with error messages [using `hx-swap` and `hx-target`].
        *   On successful update, consider redirecting to the detail view of the updated record using HTMX's `hx-redirect` or similar mechanism.
    *   **Data Handling:** Ensure the form is pre-filled with the existing data of the record.
    *   **Validation:**
        *   Implement server-side validation for all fields.
        *   Provide clear and user-friendly error messages for invalid input.

3.  **Error Handling:**
    *   Implement graceful error handling for cases where the record to be updated is not found or other server-side issues occur.

4.  **Testing Requirements**
    *   **Unit & Integration Tests:**
        *   Test that the form is correctly pre-filled with existing data.
        *   Verify that form submission via HTMX works correctly.
        *   Test various validation scenarios [e.g., valid data, invalid data, missing required fields] and ensure appropriate error messages are displayed.
        *   Test successful update and redirection to the detail view.
        *   Test edge cases, such as attempting to update a non-existent record.
    *   **End-to-End (E2E) Tests:** N/A
    *   **Manual Verification:** N/A
