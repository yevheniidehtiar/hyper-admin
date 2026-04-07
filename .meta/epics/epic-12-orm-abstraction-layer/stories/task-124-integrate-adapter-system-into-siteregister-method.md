---
type: story
id: wDJhavJtWEAW
title: "Task 1.2.4: Integrate adapter system into site.register method"
status: done
priority: medium
assignee: yevheniidehtiar
labels:
  - backend
  - task
  - registry
  - integration
  - in-progress
estimate: null
epic_ref:
  id: mpYANbVSpikQ
github:
  issue_number: 17
  repo: yevheniidehtiar/hyper-admin
  last_sync_hash: sha256:02a7598fb79091d92d7a85f7cd684d5e2e4318e932c20b737ec1139e3fcd7e89
  synced_at: 2026-04-07T17:23:23.789Z
created_at: 2025-08-23T13:54:45Z
updated_at: 2025-09-10T17:03:22Z
---

Task ID: 1.2.4
  Epic: Epic 1.2: ORM Abstraction Layer
  Phase: Phase 1: MVP Foundation
  Milestone: Issue #7
  Assigned Agent Profile: Backend Agent

  Goal
  The goal of this task is to integrate the ORM adapter system into the site.register method. This will allow HyperAdmin to seamlessly work with different ORM systems like
  SQLAlchemy and SQLModel.

  Description
  Currently, HyperAdmin has a basic site.register method that doesn't utilize the ORM abstraction layer. This task involves modifying the site.register method to:
   1. Detect the ORM used by the registered model.
   2. Select the appropriate adapter (e.g., SQLAlchemyAdapter, SQLModelAdapter).
   3. Use the adapter to create a ModelAdmin instance for the registered model.
   4. The ModelAdmin should then use the adapter for all data operations (CRUD).

  Requirements
   - The site.register method should be able to handle both SQLAlchemy and SQLModel models.
   - The ModelAdmin class should be modified to use the adapter for all database interactions.
   - The adapter should be chosen automatically based on the type of the registered model.
   - The implementation should be modular and easily extensible to support other ORMs in the future.

  Acceptance Criteria
   - When a SQLAlchemy model is registered, the SQLAlchemyAdapter is used.
   - When a SQLModel model is registered, the SQLModelAdapter is used.
   - CRUD operations (Create, Read, Update, Delete) on the registered models work correctly through the admin interface.
   - The code is well-tested and adheres to the project's coding standards.

  Dependencies
   - Task 1.2.1: Design the BaseAdapter abstract class
   - Task 1.2.2: Implement SQLAlchemyAdapter
   - Task 1.2.3: Implement SQLModelAdapter
