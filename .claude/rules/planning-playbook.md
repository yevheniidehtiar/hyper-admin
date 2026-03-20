# Agent Planning & Task Ordering Playbook

When analyzing requirements, breaking down tasks, or planning implementation (especially for complex features or multi-issue epics), you MUST follow a strictly bottom-up, architecture-first approach. 

Do not implement tasks or UI features in isolation without first ensuring the foundational architecture and domain models are in place.

## Implementation Ordering Strategy

Always order tasks, issue creation, and implementation phases in the following strict sequence:

### 1. Architecture & Domain Models (Base + Generic Components)
- **First priority**: Define the core architecture, data structures, and Pydantic/SQLAlchemy/SQLModel models.
- Build generic, reusable components that support the overarching functionality.
- Ensure the data layer and core contracts (e.g., in `core/` and `adapters/`) fully represent the domain before moving up the stack.

### 2. Business Logic & Core Workflows
- Implement the core business logic, services, orchestration, and state management relying strictly on the domain models defined in step 1.
- Write unit tests for the core logic to verify the models and domain rules independently of the web layer.

### 3. API, Middlewares & View Controllers
- Build the HTTP middlewares, view handlers (`views/`), routing, and API endpoints.
- Wire the validated business logic into the web layer. 

### 4. User Interface (UI) & HTMX
- **Last priority**: Only after the backend foundation and view controllers are solid, implement the frontend components, templates (Jinja2), and HTMX interactions.
- Ensure the UI strictly consumes the structured data and routes provided by the established models and logic.

## Why This Matters (Lessons from #115, #116, #117, #119)
Historically, attempting to implement UI, middleware, or isolated feature components without first establishing the underlying base models and business logic led to fragmented, disjointed, and broken code. An isolated approach fails because higher-level components inherently depend on a stable data contract and architecture. By enforcing a bottom-up sequence, we prevent structural debt, rework, and circular dependencies.
