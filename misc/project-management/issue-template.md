---
apply: always
---

# Issue Template

## Title: X.Y.Z: [Concise and Descriptive Title of the Task]

## Agent Persona: [Specify Agent Persona (e.g., Frontend Agent, Backend Agent, DevOps Agent, QA Agent)]

## Description

[Provide a high-level summary of the task. What is the main goal? What problem is this solving or what feature is being built? This section should provide context for the agent and link to the parent Epic.]

## Acceptance Criteria (Checklist of Sub-issues/Tasks)

[A checklist of the sub-issues or individual tasks that need to be completed for this issue. For issues that are not broken down further, this will be the functional acceptance criteria. The parent issue's acceptance criteria serve as a roll-up, ensuring all child tasks are complete and verified, or that necessary follow-ups are created.]

- [ ] Sub-issue X.Y.Z.A: [Sub-issue Name]
- [ ] Sub-issue X.Y.Z.B: [Another Sub-issue Name]
- [ ] All sub-issues are completed and verified.
- [ ] Any necessary follow-up issues for updates, fixes, or refactors have been created and linked.

## Task Decomposition and Sub-Issue Strategy

**Objective:** To ensure tasks are manageable, mitigate risks from long-running processes, and maintain high-quality
output, it is crucial to decompose large or complex tasks into smaller, sequential sub-issues.

**Guidelines for Task Decomposition:**

1. **Initial Assessment:** Upon receiving a new issue, the assigned agent must first assess its complexity. If the task
   is expected to take a significant amount of time (e.g., more than a few hours), involves multiple distinct
   components, or has a high degree of uncertainty, it **must** be broken down into sub-issues using the
   `Sub-issue Template`.

2. **Linking:** Sub-issues should be clearly linked to this parent issue.

## Additional Guidance for Agent

1. **Implementation Details & Technical Stack:**
    * **Architecture & Patterns:
      ** [Describe any architectural patterns to follow (e.g., MVC, Repository Pattern) or existing structures to use. Refer to Epic-level guidance for broader context.]
    * **Technologies/Libraries:
      ** [Specify the core technologies, libraries, or frameworks to be used (e.g., React, Django, Docker, HTMX, etc.). Refer to Epic-level guidance for broader context.]
    * **Existing Code/Components:
      ** [Mention any existing modules, components, templates (e.g., 'form_layout.html'), or functions that should be reused or leveraged to ensure consistency.]
    * **New Components:
      ** [If applicable, specify any new reusable components, templates, or modules that need to be created.]

2. **Core Requirements & Business Logic:**
    * **Functionality:
      ** [List the primary functional requirements. What must the feature do? Detail specific business rules, data transformations, or user interaction flows.]
    * **Data Handling:
      ** [Describe how data should be created, read, updated, or deleted. Specify any API endpoints to be used or created (e.g., POST to /api/models/).]
    * **Validation:
      ** [Detail the server-side and/or client-side validation rules for any inputs. Provide examples of valid and invalid data.]

3. **Error Handling:**

[Describe how the system should gracefully handle potential errors, exceptions, or edge cases. For example, specify responses for API failures, database connection issues, or failed validation.]

4. **Testing Requirements**

    * **Unit & Integration Tests:**
      [Specify the scope of unit and integration tests. Detail the key functions, classes, modules, or API endpoints that must be covered.]
      Instruction: Write all necessary tests and ensure they pass before marking the issue as complete.

    * **End-to-End (E2E) Tests:**
      [Describe the user scenarios that need to be covered by E2E tests.]
      Tools: [Specify the E2E testing framework to use (e.g., Playwright, Cypress, Selenium).]
      Execution
      Instructions: [Provide any special instructions regarding the execution of these tests (e.g., "Write the tests but do not run them if you are Agent <X>", or "E2E tests should only be run against the staging environment").]

    * **Manual Verification:**
      [List key scenarios to be manually verified to ensure the user experience and functionality meet expectations.]
