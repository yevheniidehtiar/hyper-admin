---
type: epic
id: FHLoHjc9lTvN
title: "Epic 1.5: Authorization and User Management"
status: done
priority: medium
owner: null
labels:
  - enhancement
  - backend
  - core
milestone_ref:
  id: 15wIehkIIVtT
github:
  issue_number: 77
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:0ce89f5b503f551e51c3d562a151ad128283a1ee9a657697ec0588ae4daafb41
  synced_at: 2026-04-05T09:13:33.559Z
created_at: 2025-09-10T17:59:10Z
updated_at: 2026-03-20T15:27:00Z
---


**Goal:** To implement robust authentication, user management, and permission control to secure the HyperAdmin interface and provide granular access control.

**Key Areas / High-Level Tasks:**

1.  **Admin Authentication:**
    *   Implement a secure admin login page.
    *   Establish session management for authenticated users.
    *   Handle password hashing and verification.

2.  **User Management:**
    *   Define database models for `User` entities (e.g., username, password hash, email, active status).
    *   Implement basic CRUD operations for users within the admin interface.

3.  **Group and Permission Management:**
    *   Define database models for `Group` and `Permission` entities.
    *   Establish relationships between Users, Groups, and Permissions (e.g., many-to-many).
    *   Implement mechanisms to assign permissions to users directly or via groups.
    *   Provide an interface within the admin for managing groups and permissions.

4.  **Authorization Logic:**
    *   Integrate authorization checks into existing and future views/endpoints to restrict access based on user roles and permissions.
    *   Implement decorators or middleware for easy application of authorization rules.

5.  **CLI Tools:**
    *   Develop a command-line interface tool (e.g., `hyperadmin createsuperuser`) to create initial admin users with passwords.

**Milestone Proposal:** `Phase 2: Core Feature Parity` (as this is a fundamental feature for a functional admin panel)

**Potential Considerations / Discussion Points:**

*   **Authentication Strategy:** Session-based (cookies) vs. Token-based (JWT) for the admin interface.
*   **Password Hashing:** Which secure hashing algorithm to use (e.g., bcrypt, Argon2).
*   **Database Integration:** How these new models will integrate with the existing `SQLModel` setup.
*   **UI/UX:** Design considerations for the login page and user/group/permission management interfaces.
*   **Error Handling:** Consistent error responses for authentication/authorization failures.
