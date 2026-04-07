---
type: story
id: 4CgQJsUtWRZh
title: "1.4.4.1: Implement the update view template"
status: done
priority: medium
assignee: null
labels: []
estimate: null
epic_ref:
  id: h790OIFo40LW
github:
  issue_number: 111
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:c6588ebc57e7bd2283a96efaf3b0cd57564b31af924a30e70b612c1d911c013d
  synced_at: 2026-04-07T17:23:23.790Z
created_at: 2025-09-21T16:48:17Z
updated_at: 2026-03-17T21:57:45Z
---

**Issue Title:** 1.4.4.1: Implement the update view template

**Agent Persona:** Frontend Agent

**Description**

Implement the update view template, which will be used to display a form for editing existing records. This template will be the foundation for modifying existing data in the system.

**Acceptance Criteria**

*   [ ] An `update.html` template is created in `src/hyperadmin/templates/`.
*   [ ] The template extends `form_layout.html`.
*   [ ] The template displays a form with all the fields for a given model.
*   [ ] The form is pre-filled with the existing data of the record.
*   [ ] The form includes a "Save" button.

**Additional Guidance for Agent**

1.  **Implementation Details & Technical Stack:**
    *   **Architecture & Patterns:** The template should follow the established Jinja2 and HTMX patterns.
    *   **Technologies/Libraries:** Jinja2, HTMX.
    *   **Existing Code/Components:** `form_layout.html`.
    *   **New Components:** N/A.

2.  **Core Requirements & Business Logic:**
    *   **Functionality:** The template should dynamically render a form for any registered model.
    *   **Data Handling:** The form will be used to submit updated data to the backend.
    *   **Validation:** N/A.

3.  **Error Handling:**
    *   N/A.

4.  **Testing Requirements**
    *   **Unit & Integration Tests:**
        *   Test that the template renders correctly for a sample model.
        *   Test that the form is correctly pre-filled with existing data.
    *   **End-to-End (E2E) Tests:** N/A.
    *   **Manual Verification:**
        *   Verify that the update view displays correctly for a sample model.
