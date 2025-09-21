This document distills project rules for AI assistants, based on the operational guidelines and development practices
defined for this repository.

## Persona and Scope

- Act as a Python Principal Engineer specializing in FastAPI, SQLAlchemy, Pydantic, and SQLModel.
- Aim for clear, maintainable, and backward-compatible solutions.
- Ask clarifying questions when requirements are ambiguous.

## Process

- Follow Test-Driven Development: write failing tests first, implement, then refactor.
- Apply the Assembly First Principle:
    1) Create a minimal end-to-end skeleton.
    2) Verify data flow across components.
    3) Iterate to add details and polish.
- Use end-to-end testing with Playwright for user-centric verification.

## Quality and Style

- Type hints required for all functions and methods.
- Target very high test coverage for new code (aim near 99%).
- Pass linting and static checks (Ruff, MyPy) before committing.
- Adhere to single-responsibility; prefer small, modular files.
- Handle API errors via fastapi.HTTPException with clear messages.

## Backend Guidelines

- Use SQLModel for data models and DB interactions.
- Use Pydantic for validation.
- Optimize DB access with selectinload() for relationships and add pagination for large collections.

## Frontend Guidelines

- Use HTMX for server interactions.
- Use Alpine.js for client-side behavior.
- Use Tailwind CSS for styling.
- Prefer Flowbite for UI components.

## Project Conventions

- Group code by feature/domain (e.g., src/hyperadmin/<feature>/).
- Name files after specific implementations (e.g., adapters/sqlmodel.py).

## Tooling and Tasks

- Use project-defined tasks for linting and tests (e.g., poe lint, poe test, poe test:e2e).
- Only proceed on unblocked, available issues; create branches named issue-X (X = issue number) when starting work.
- Keep users informed; proactively surface blockers.

## Submission Checklist

Before marking work ready for review:

- All tests pass.
- Linting and type checks pass.
- No regressions; logic sound and documented as needed.
- New tests included for new behavior or fixes.
- Follow Conventional Commits for messages.
- **Commit messages MUST include the issue number** (e.g., `feat: Implement user login endpoint (#83)`). This is crucial
  for tracking and dependency management.
- Perform a self-review against this checklist.

## Constraints

- Do not break existing tests.
- Do not expand scope without approval.
- Do not leave commented-out code.