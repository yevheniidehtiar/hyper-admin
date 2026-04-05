---
type: story
id: QB5gI7iO2TkE
title: "1.4.2.3: Add sorting to the list view"
status: done
priority: medium
assignee: null
labels: []
estimate: null
epic_ref: null
github:
  issue_number: 105
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:b9f7af9f34ef589b32b342623fdbb340466f7b225a79d82a19c8ca622dfe274b
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2025-09-21T16:48:02Z
updated_at: 2026-03-19T20:13:54Z
---

**Issue Title:** 1.4.2.3: Add sorting to the list view

**Agent Persona:** Frontend Agent

**Description**

Add sorting functionality to the list view to allow users to sort the records by different columns. This will improve the usability of the list view by allowing users to organize the data as they see fit.

**Acceptance Criteria**

*   [ ] The column headers in the list view are clickable links.
*   [ ] Clicking on a column header sorts the records by that column in ascending order.
*   [ ] Clicking on the same column header again sorts the records in descending order.
*   [ ] The sorting is done using HTMX, without a full page reload.
*   [ ] The current sort order is indicated in the UI (e.g., with an arrow icon).

**Additional Guidance for Agent**

**Before implementing, ensure to check existing functionality related to list views to maintain consistency and avoid redundancy.**

1.  **Implementation Details & Technical Stack:**
    *   **Architecture & Patterns:** The sorting logic should be implemented on the backend.
    *   **Technologies/Libraries:** Jinja2, HTMX.
    *   **Existing Code/Components:** `list.html`.
    *   **New Components:** A `sortable_header.html` component might be useful.

2.  **Core Requirements & Business Logic:**
    *   **Functionality:** The sorting should work for all sortable columns in the model.
    *   **Data Handling:** The backend should handle the sorting logic and return the sorted data.
    *   **Validation:** N/A.

3.  **Error Handling:**
    *   N/A.

4.  **Testing Requirements**
    *   **Unit & Integration Tests:**
        *   Test that clicking on a column header sorts the records correctly.
        *   Test that the sort order is toggled correctly on subsequent clicks.
    *   **End-to-End (E2E) Tests:** N/A.
    *   **Manual Verification:**
        *   Verify that sorting works correctly for different columns and data types.
