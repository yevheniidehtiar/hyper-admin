# Gemini Guidelines

This file contains guidelines for the Gemini project.

## Development Process

*   **Task Management:** All tasks are managed as GitHub issues. New tasks should be created using the GitHub MCP.
*   **Progressive Enhancement:** Build features starting with functional HTML. Enhance the user experience by layering HTMX for dynamic interactions and Alpine.js for complex client-side behaviors.

## Code Quality and Style

*   **Type Safety:** All functions and methods must include type hints.
*   **Test Coverage:** Strive for 99% test coverage for all new code.
*   **Linting and Formatting:** Ensure all code passes Ruff and MyPy checks before committing.
*   **Modularity:** Adhere to the single responsibility principle. Keep components in separate files and aim for files under 200 lines.
*   **Error Handling:** Use `fastapi.HTTPException` to handle errors gracefully and provide clear feedback to the user.

## Python and FastAPI

*   **Data Modeling:** Use `SQLModel` for defining and interacting with database models.
*   **Data Validation:** Use `Pydantic` for robust data validation.
*   **Database Performance:** Use `selectinload()` for eager loading of related data and implement pagination for large datasets.

## Frontend

*   **Server Interactions:** Use HTMX for all server interactions.
*   **Client-Side Scripting:** Use Alpine.js for all client-side scripting.
*   **Styling:** Use Tailwind CSS for all styling.
*   **UI Components:** Use the Flowbite UI component library.

---
I understand and have updated my internal guidelines. Here is a summary of my new process:

    Check GitHub Issues: When given a task with a keyword, I will first check the GitHub issues for a corresponding issue.
    Branch Creation: After the plan is approved, I will create a new empty branch named issue-X (where X is the issue number) and push it to the repository immediately.
    Issue Selection Criteria: I will only work on issues that meet the following criteria:
        No blockers listed in the description.
        No "in-progress" label.
        No existing branch with the name issue-X.
    Passed `poe lint` and `poe test` are mandatory before put task "Ready for review".