---
apply: always
---

Issue Template for Project Manager Agent
Issue Title: [Concise and Descriptive Title of the Task]

Agent Persona: [Specify Agent Persona (e.g., Frontend Agent, Backend Agent, DevOps Agent, QA Agent)]

Description

[Provide a high-level summary of the task. What is the main goal? What problem is this solving or what feature is being built? This section should provide context for the agent.]

Acceptance Criteria

[Provide a clear, concise, and testable list of conditions that must be met for the task to be considered complete. This defines what "done" looks like.]

[ ] Criterion 1: e.g., A user can access the new page at the /models/create endpoint.

[ ] Criterion 2: e.g., Submitting the form with valid data creates a new record in the database.

[ ] Criterion 3: e.g., Submitting the form with invalid data displays specific error messages next to the relevant
fields without a full page reload.

[ ] Criterion 4: e.g., All new code is covered by unit tests that pass in the CI/CD pipeline.

Additional Guidance for Agent

1. Implementation Details & Technical Stack:

Architecture &
Patterns: [Describe any architectural patterns to follow (e.g., MVC, Repository Pattern) or existing structures to use.]

Technologies/Libraries: [Specify the core technologies, libraries, or frameworks to be used (e.g., React, Django, Docker, HTMX, etc.).]

Existing
Code/Components: [Mention any existing modules, components, templates (e.g., 'form_layout.html'), or functions that should be reused or leveraged to ensure consistency.]

New Components: [If applicable, specify any new reusable components, templates, or modules that need to be created.]

2. Core Requirements & Business Logic:

Functionality: [List the primary functional requirements. What must the feature do? Detail specific business rules, data transformations, or user interaction flows.]

Data
Handling: [Describe how data should be created, read, updated, or deleted. Specify any API endpoints to be used or created (e.g., POST to /api/models/).]

Validation: [Detail the server-side and/or client-side validation rules for any inputs. Provide examples of valid and invalid data.]

3. Error Handling:

[Describe how the system should gracefully handle potential errors, exceptions, or edge cases. For example, specify responses for API failures, database connection issues, or failed validation.]

4. Testing Requirements

Unit & Integration Tests:

[Specify the scope of unit and integration tests. Detail the key functions, classes, modules, or API endpoints that must be covered.]

Instruction: Write all necessary tests and ensure they pass before marking the issue as complete.

End-to-End (E2E) Tests:

[Describe the user scenarios that need to be covered by E2E tests.]

Tools: [Specify the E2E testing framework to use (e.g., Playwright, Cypress, Selenium).]

Execution
Instructions: [Provide any special instructions regarding the execution of these tests (e.g., "Write the tests but do not run them if you are Agent <X>", or "E2E tests should only be run against the staging environment").]

Manual Verification:

[List key scenarios to be manually verified to ensure the user experience and functionality meet expectations.]