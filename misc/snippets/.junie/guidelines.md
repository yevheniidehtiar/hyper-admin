# SQLAdmin-HTMX Junie Guidelines

## Project Overview
Modern admin interface for SQLModel-based models built on FastAPI with HTMX, Alpine.js, and Tailwind CSS.

**Current Stack:** Python 3.9+, FastAPI, SQLModel, HTMX, Alpine.js, Tailwind CSS  
**Deprecated:** Starlette, WTForms, jQuery, Bootstrap/Tabler

## Core Principles

### 1. Progressive Enhancement
- Start with working HTML forms
- Layer HTMX for dynamic interactions
- Use Alpine.js for complex client-side behavior
- Maintain accessibility and graceful degradation

### 2. Code Quality
- All functions must have type hints
- 99% test coverage requirement
- Proper docstrings for public APIs
- Pass Ruff and MyPy checks


### Decoupling Rules
- One component per file (CSS + JS)
- Separate page-specific from reusable code
- Keep files under 200 lines
- Single responsibility principle

## Code Style Conventions

## Testing & Performance

### Performance
- Use `selectinload()` for eager loading
- Implement pagination for large datasets
- Cache frequently accessed data
- Use HTMX for partial updates only

## Security Checklist
- CSRF tokens in all forms
- Input validation with Pydantic
- Escape user output: `{{ user.name|e }}`
- Use HTTPS in production
- Validate file uploads properly

## Development Commands
```bash
uv run python          # Run Python
uv run pytest          # Run tests  
hatch run test:test     # Run linter
uv run uvicorn main:app # Run FastAPI


```

## E2E Testing
For detailed E2E testing and debugging workflow, see: [./e2e-test-guidelines.md](./e2e-test-guidelines.md)

## More guidelines links
[multi-agent-task-guidelines.md](multi-agent-task-guidelines.md)
[stack-guidelines.md](stack-guidelines.md)
[code-style-conventions.md](code-style-conventions.md)
