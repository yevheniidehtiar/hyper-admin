## Task Coordination System

### .tasks Directory - "Jira for AI"
The `.tasks/` directory serves as a task management system for coordinating work across multiple Junie agents. It contains:

- **Epic-based organization**: Tasks grouped by feature/epic (e.g., `stack-deprecation-epic/`, `e2e-test-plans-epic/`)
- **Parallel execution planning**: Tasks designed for concurrent agent work with dependency tracking
- **Scope evaluation**: Each task includes time estimates and impact assessment to minimize conflicts
- **Status tracking**: Clear progress indicators and completion criteria

**Key Benefits:**
- Zero or minimal impact on parallel execution through proper task scoping
- Clear dependencies and execution order recommendations
- Reusable components and shared patterns documented
- Self-contained tasks with complete context and success criteria

**Before starting work**: Always check `.tasks/` for related ongoing work and coordination requirements.
