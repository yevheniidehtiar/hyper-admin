# HyperAdmin Product Roadmap

This document outlines the planned features and development phases for HyperAdmin. Our goal is to build a modern, powerful, and easy-to-use admin interface for FastAPI.

---

## ✅ Phase 1: Foundation & The "Walking Skeleton" (Completed)

This initial phase established the project's foundation, including the repository setup, a basic "walking skeleton" of the application, and a CI/CD pipeline. This work proved the core concept and allowed for rapid development.

---

## 🟡 Phase 2: Core Functionality & Admin UI (In Progress)

The goal of this phase is to build a complete and visually appealing admin interface with full CRUD functionality and a modern UI.

- **CRUD Implementation**:
    - [x] Add SQLAlchemy and SQLModel as dependencies.
    - [x] Refactor `ModelView` to work with SQLModel classes.
    - [x] Implement **Create View** with dynamic form generation.
    - [x] Implement **Update View** with pre-filled forms.
    - [x] Implement **Delete Action** with HTMX for a seamless UI experience.

- **Admin UI Epics**:
    - [/] **Navigation Sidebar**: Design and implement a collapsible sidebar for easy navigation between different admin views. (Basic implementation exists)
    - [x] **Data Table Component**: Create a reusable and feature-rich data table with sorting, pagination, and filtering capabilities.
    - [x] **Forms & Widgets**: Develop a set of standardized form elements and dashboard widgets for a consistent and modern look and feel.
    - [x] **Styling & Theming**: Implement a clean and modern design system, with support for custom theming.

- **Documentation & Community Outreach**:
    - [x] Set up a documentation site using MkDocs with the `mkdocs-material` theme.
    - [ ] Write a "Getting Started" tutorial and document the core classes.
    - [ ] Create a complete, runnable project in the `examples/` directory.
    - [ ] Announce v0.2.0 on relevant platforms (GitHub Discussions, Twitter, Reddit).

---

## ⚪️ Phase 3: Advanced Features & Polish (Future)

With a solid foundation and a polished UI, this phase will focus on adding advanced features and making HyperAdmin even more powerful and flexible.

- **Advanced Features**:
  - [ ] Authentication and authorization hooks.
  - [ ] Support for model relationships (e.g., dropdowns for foreign keys).
  - [ ] Custom actions (e.g., "approve selected items").
  - [ ] File uploads.
  - [ ] Advanced form validation and error handling.
  - [ ] UI/UX Polish (e.g., pagination, notifications).