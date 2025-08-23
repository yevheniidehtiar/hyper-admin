# HyperAdmin Product Roadmap

This document outlines the planned features and development phases for HyperAdmin. Our goal is to build a modern, powerful, and easy-to-use admin interface for FastAPI.

---

## ✅ Phase 1: Foundation & The "Walking Skeleton" (Complete)

The goal of this phase was to create a minimal, working version that proves the concept and excites early adopters.

- **Repository Setup**:
  - [x] Initialize Git repository.
  - [x] Create standard Python project structure: `src/hyperadmin/`, `tests/`, `docs/`, `examples/`.
  - [x] Add `pyproject.toml` with initial dependencies.
  - [x] Add MIT License.
  - [x] Create `README.md`, `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md`.
- **"Walking Skeleton" Implementation**:
  - [x] Core `Admin` class that can be mounted onto a FastAPI application.
  - [x] Basic `ModelView` that accepts a Pydantic model.
  - [x] Read-Only List View.
  - [x] Read-Only Detail View.
  - [x] Frontend Scaffolding with Jinja2, HTMX, and Tailwind CSS (via CDN).
- **CI/CD Pipeline**:
  - [x] Set up and debug the initial CI pipeline to ensure formatting, linting, and tests are passing across multiple Python versions.

---

## Phase 2: Core Functionality & First Announcement (In Progress)

The goal of this phase is to make HyperAdmin truly useful by adding database support and full CRUD (Create, Read, Update, Delete) functionality.

- **Database Integration & CRUD**:
  - [ ] Add SQLAlchemy and SQLModel as dependencies.
  - [ ] Refactor `ModelView` to work with SQLModel classes, fetching data from a database (e.g., SQLite).
  - [ ] Implement **Create View**: Dynamically generate an HTML `<form>` from a Pydantic/SQLModel model.
  - [ ] Implement **Update View**: Similar to the create view, but pre-filled with existing data.
  - [ ] Implement **Delete Action**: Use an HTMX request (`hx-delete`) to remove an item from the database and the UI without a full page reload.

- **Documentation & Community Outreach**:
  - [ ] Set up a documentation site using MkDocs with the `mkdocs-material` theme.
  - [ ] Write a "Getting Started" tutorial and document the core classes.
  - [ ] Create a complete, runnable project in the `examples/` directory.
  - [ ] Announce v0.2.0 on relevant platforms (GitHub Discussions, Twitter, Reddit).

---

## Phase 3: Polish & Advanced Features (Future)

With a working and documented project, this phase will focus on making HyperAdmin robust and powerful.

- **Advanced Features**:
  - [ ] Authentication and authorization hooks.
  - [ ] Support for model relationships (e.g., dropdowns for foreign keys).
  - [ ] Search and filtering on the list view.
  - [ ] Custom actions (e.g., "approve selected items").
  - [ ] File uploads.
  - [ ] Advanced form validation and error handling.
  - [ ] UI/UX Polish (e.g., pagination, notifications).
