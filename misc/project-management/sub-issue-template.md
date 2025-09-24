---
apply: always
---

# Sub-issue Template

## Title: X.Y.Z.A: [Sub-issue Name]

## Agent Persona: [Specify Agent Persona (e.g., Frontend Agent, Backend Agent, DevOps Agent, QA Agent)]

## Description

[A very specific, atomic task that contributes to a larger Issue. This should be a single, clearly defined piece of work.]

## Acceptance Criteria

[Detailed, testable conditions that must be met for this specific sub-task to be considered complete. This defines what "done" looks like for this granular piece of work.]

- [ ] Criterion 1: e.g., The `create.html` template includes an `hx-post` attribute pointing to the correct endpoint.
- [ ] Criterion 2: e.g., The `name` input field is pre-filled with the value from the model instance.

## Additional Guidance for Agent

1. **Implementation Details & Technical Stack:**
    * **Architecture & Patterns:** [Specific architectural patterns or existing structures to follow for this sub-task.]
    * **Technologies/Libraries:** [Specific technologies, libraries, or frameworks to be used for this sub-task.]
    * **Existing Code/Components:
      ** [Mention any existing modules, components, templates, or functions that should be reused or leveraged for this sub-task.]
    * **New Components:
      ** [If applicable, specify any new reusable components, templates, or modules that need to be created for this sub-task.]

2. **Core Requirements & Business Logic:**
    * **Functionality:** [The primary functional requirements for this sub-task.]
    * **Data Handling:** [How data should be created, read, updated, or deleted for this sub-task.]
    * **Validation:** [Server-side and/or client-side validation rules for any inputs specific to this sub-task.]

3. **Error Handling:**
   [How the system should gracefully handle potential errors, exceptions, or edge cases specific to this sub-task.]

4. **Testing Requirements**
    * **Unit & Integration Tests:**
      [Specify the scope of unit and integration tests for this sub-task. Detail the key functions, classes, modules, or API endpoints that must be covered.]
      Instruction: Write all necessary tests and ensure they pass before marking the sub-issue as complete.
    * **End-to-End (E2E) Tests:**
      [Describe the user scenarios that need to be covered by E2E tests for this sub-task.]
      Tools: [Specify the E2E testing framework to use (e.g., Playwright, Cypress, Selenium).]
      Execution Instructions: [Provide any special instructions regarding the execution of these tests.]
    * **Manual Verification:**
      [List key scenarios to be manually verified for this sub-task.]
