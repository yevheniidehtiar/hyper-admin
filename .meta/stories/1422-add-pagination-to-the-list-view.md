---
type: story
id: VvVFKprhuyFY
title: "1.4.2.2: Add pagination to the list view"
status: done
priority: medium
assignee: null
labels: []
estimate: null
epic_ref: null
github:
  issue_number: 104
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:024f2448a75a99f4c87480a4eaff48e7de27170304fbfe9112c24ac377a75d81
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2025-09-21T16:48:01Z
updated_at: 2026-03-19T20:13:51Z
---

**Issue Title:** 1.4.2.2: Add pagination to the list view

**Agent Persona:** Frontend Agent

**Description**

Add pagination to the list view to handle large datasets. This will improve the performance and usability of the list view when dealing with a large number of records.

**Acceptance Criteria**

*   [ ] The list view displays a pagination component when the number of records exceeds the page size.
*   [ ] The pagination component allows users to navigate to the next, previous, first, and last pages.
*   [ ] The pagination component correctly updates the list of records using HTMX, without a full page reload.

**Additional Guidance for Agent**

**Before implementing, ensure to check existing functionality related to list views to maintain consistency and avoid redundancy.**

1.  **Implementation Details & Technical Stack:**
    *   **Architecture & Patterns:** The pagination component should be a reusable Jinja2 component.
    *   **Technologies/Libraries:** Jinja2, HTMX.
    *   **Existing Code/Components:** `list.html`.
    *   **New Components:** A `pagination.html` component.

2.  **Core Requirements & Business Logic:**
    *   **Functionality:** The pagination should be implemented on the backend and exposed to the frontend.
    *   **Data Handling:** The backend should provide the necessary pagination data (e.g., total pages, current page).
    *   **Validation:** N/A.

3.  **Error Handling:**
    *   N/A.

4.  **Testing Requirements**
    *   **Unit & Integration Tests:**
        *   Test that the pagination component is displayed when there are multiple pages of records.
        *   Test that the pagination links work correctly and update the list of records.
    *   **End-to-End (E2E) Tests:** N/A.
    *   **Manual Verification:**
        *   Verify that the pagination works correctly for a model with a large number of records.
