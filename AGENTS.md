# AI Agent Guidelines

Welcome, agent! This document provides guidelines for working on this project.

This project is a Python `package` generated from a template. It is configured with a `` development environment.

## Project Structure

The main source code for this project is located in the `src/hyperadmin` directory. Tests are in the `tests/` directory.

## Dependency Management

This project uses `uv` for dependency management. Dependencies are defined in `pyproject.toml`.

To install all dependencies, including development dependencies, run:

```bash
uv pip install -e .[dev]
```

## Task Runner: Poe the Poet

This project uses `poethepoet` as a task runner. You can see the available tasks in the `[tool.poe.tasks]` section of `pyproject.toml`.

To run a task, use `poe <task_name>`. For example:
- `poe lint`: Run linters.
- `poe test`: Run unit and integration tests.
- `poe test:e2e`: Run end-to-end tests.

## Development Process

This project advocates for a development process that prioritizes robust testing and early integration.

### The Assembly First Principle

Instead of building hyper-detailed components in isolation, we follow the **Assembly First Principle**. This means:

1.  **Build a Skeleton First**: Start by creating a simple, end-to-end, working version of the entire feature. Use placeholders, stubs, or simplified versions of components.
2.  **Define Data Flow**: Focus on how data moves through the system from one component to another.
3.  **Assemble and Verify**: Connect these simple components to create a functional, end-to-end skeleton. This provides a working version of the feature very early.
4.  **Iterate and Add Detail**: Once the overall structure is in place and working, go back and flesh out the details of each component, adding complexity, UI polish, and final logic.

This approach helps discover integration risks early, allows for earlier feedback, and results in a more cohesive system.

### Test-Driven Development (TDD)

Combine the Assembly First Principle with TDD. For each component you are fleshing out, write a failing test first, then write the code to make it pass, and finally refactor.

### End-to-End Testing with Playwright

All features should be tested from the user's perspective. This project is set up with Playwright for end-to-end testing.

**Running E2E Tests:**
To run the entire E2E test suite, use the following command:
```bash
poe test:e2e
```
This will install the necessary browser dependencies and run the tests located in `tests/e2e`.

**Interactive Development and Debugging:**
You are encouraged to use Playwright not just for final tests, but as a development tool. Use its features like the Trace Viewer and headed mode to interactively build and debug your feature from the UI down.





## Submitting Changes

This project follows the Conventional Commits specification. When you are ready to submit your work, please use `cz bump` to create a compliant commit message.

---
I understand and have updated my internal guidelines. Here is a summary of my new process:

    Check GitHub Issues: When given a task with a keyword, I will first check the GitHub issues for a corresponding issue.
    Branch Creation: After the plan is approved, I will create a new empty branch named issue-X (where X is the issue number) and push it to the repository immediately.
    Issue Selection Criteria: I will only work on issues that meet the following criteria:
        No blockers listed in the description.
        No "in-progress" label.
        No existing branch with the name issue-X.
