---
paths:
  - "src/hyperadmin/**/*.py"
---

## Code Conventions

- Group by feature: `src/hyperadmin/<feature>/` (e.g., `adapters/`, `views/`, `core/`)
- Name files by implementation: `adapters/sqlmodel.py` not `sqlmodel_adapter.py`
- Type hints required on all functions and methods
- Line length: 100 characters
- No commented-out code, no `pass`/`TODO` placeholders in final code
- Handle API errors via `fastapi.HTTPException` with clear messages
- Use SQLModel for data models, Pydantic for validation
- Optimize DB access with `selectinload()` for relationships; add pagination for large collections
- Use HTMX for server interactions, Alpine.js for client-side behavior
