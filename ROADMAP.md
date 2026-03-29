# HyperAdmin Product Roadmap

This document outlines the planned features and development phases for HyperAdmin. Our goal is to build a modern, powerful, and easy-to-use admin interface for FastAPI.

> **For detailed epic-level planning, milestone tracking, and priority matrix, see [`docs/roadmap.md`](docs/roadmap.md).**

---

## Phase 1: Foundation & The "Walking Skeleton" (Completed)

This initial phase established the project's foundation, including the repository setup, a basic "walking skeleton" of the application, and a CI/CD pipeline. This work proved the core concept and allowed for rapid development.

---

## Phase 2: Core Functionality & Admin UI (Completed)

This phase built a complete and visually appealing admin interface with full CRUD functionality and a modern UI.

- **CRUD Implementation**:
    - [x] Add SQLAlchemy and SQLModel as dependencies.
    - [x] Refactor `ModelView` to work with SQLModel classes.
    - [x] Implement **Create View** with dynamic form generation.
    - [x] Implement **Update View** with pre-filled forms.
    - [x] Implement **Delete Action** with HTMX for a seamless UI experience.

- **Admin UI Epics**:
    - [x] **Navigation Sidebar**: Collapsible sidebar for easy navigation between different admin views.
    - [x] **Data Table Component**: Reusable and feature-rich data table with sorting, pagination, and filtering.
    - [x] **Forms & Widgets**: Standardized form elements including select/multiselect widgets (enum, FK, M2M, autocomplete).
    - [x] **Styling & Theming**: Clean and modern design system with theme support.
    - [x] **Custom Actions Framework**: Register and execute custom actions per model.
    - [x] **Fieldsets**: Group fields in admin forms with collapsible sections.
    - [x] **WCAG 2.1 AA Accessibility**: Keyboard navigation, ARIA, color contrast, screen reader support.

- **Documentation & Community Outreach**:
    - [x] Set up a documentation site using MkDocs with the `mkdocs-material` theme.
    - [ ] Write a "Getting Started" tutorial and document the core classes.
    - [ ] Create a complete, runnable project in the `examples/` directory.
    - [ ] Announce v0.2.0 on relevant platforms (GitHub Discussions, Twitter, Reddit).

---

## Phase 3: Advanced Features & Polish (Future)

With a solid foundation and a polished UI, this phase will focus on adding advanced features and making HyperAdmin even more powerful and flexible.

- **Advanced Features**:
  - [ ] Authentication and authorization hooks (E2E wiring).
  - [x] Support for model relationships (select/multiselect widgets with FK, M2M, autocomplete).
  - [x] Custom actions (action framework with bulk and single-object actions).
  - [ ] File uploads.
  - [ ] Zero-config admin (3 lines of code).
  - [ ] Internationalization (i18n).
  - [ ] Audit / activity log.
  - [ ] Dashboard builder.
  - [ ] Real-time updates (WebSocket).
  - [ ] Plugin & extension system.
