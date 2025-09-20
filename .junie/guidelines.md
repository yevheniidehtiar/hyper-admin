# HyperAdmin Project Guidelines

## Project Overview
HyperAdmin is a modern, Pydantic-native admin interface for FastAPI, powered by HTMX. This project provides a clean, maintainable admin interface that integrates seamlessly with FastAPI applications using SQLModel and SQLAlchemy.

## Project Structure

The project follows a feature-based organization under `src/hyperadmin/`:

```
src/hyperadmin/
├── core/              # Core functionality
│   ├── __init__.py
│   ├── adapters.py    # Base adapter interfaces
│   ├── app.py         # Main application logic
│   ├── discovery.py   # Model discovery utilities
│   ├── model.py       # Core model definitions
│   ├── options.py     # Configuration options
│   └── registry.py    # Component registry
├── adapters/          # Database adapters
│   ├── __init__.py
│   ├── registry.py    # Adapter registry
│   ├── sqlalchemy.py  # SQLAlchemy adapter
│   └── sqlmodel.py    # SQLModel adapter
├── views/             # UI views
│   ├── __init__.py
│   ├── dynamic.py     # Dynamic content views
│   └── static.py      # Static content views
├── __init__.py
├── db.py              # Database utilities
├── discover.py        # Discovery functionality
├── main.py            # Main entry point
└── routing.py        # Route definitions
```

### Naming Conventions
- **Group by Feature**: Place related modules into subdirectories named after their purpose (e.g., `src/hyperadmin/adapters/`)
- **Specific File Names**: Name files within subdirectories after their specific implementation (e.g., `sqlmodel.py`)
- **Example**: Prefer `src/hyperadmin/adapters/sqlmodel.py` over `src/hyperadmin/sqlmodel_adapter.py`

## Development Workflow

### Prerequisites
- Python 3.10+
- `uv` package manager
- Node.js (for Tailwind CSS builds)

### Environment Setup
```bash
# Create and install virtual environment
uv sync --python 3.10 --all-extras

# Activate the virtual environment
source .venv/bin/activate

# Install pre-commit hooks
pre-commit install --install-hooks
```

### Development Process
You must follow a **Test-Driven Development (TDD)** approach:

1. **Write a failing test** that captures the requirements
2. **Write the minimal code** to make the test pass  
3. **Refactor** for clarity and efficiency

### Assembly First Principle
To mitigate integration risks early:

1. **Build a Skeleton First**: Start with a simple, end-to-end working version using placeholders/stubs
2. **Define and Verify Data Flow**: Focus on how data moves through the system
3. **Iterate and Add Detail**: Once the structure is verified, flesh out component details
2. **Write the minimal code** to make the test pass  
## Testing Requirements

### Test Execution
**MANDATORY**: You must run both linting and tests before submitting any changes:

```bash
# Run linters (must pass)
poe lint

# Run all tests (must pass)
poe test
```

### Test Types
1. **Unit Tests**: `poe test:unit` - Run with pytest on `tests/unit/`
2. **End-to-End Tests**: `poe test:e2e` - Run with Playwright on `tests/e2e/`

### Test Structure
- Unit tests: `tests/unit/`
- E2E tests: `tests/e2e/`
- All features must be tested from the user's perspective using Playwright

## Task Management

This project uses **Poe the Poet** for task automation. Key tasks:

```bash
poe                    # List all available tasks
poe lint              # Run linters and code formatting
poe test              # Run unit and e2e tests
poe test:unit         # Run unit tests only
poe test:e2e          # Run end-to-end tests with Playwright
poe docs:serve        # Serve documentation locally
poe docs:build        # Build documentation
poe security-check    # Run security and license checks
poe static:build-css  # Build Tailwind CSS using Docker
```

## Code Quality Standards

### Linting and Formatting
- **Ruff**: Used for linting and formatting (configured in `pyproject.toml`)
- **MyPy**: Type checking
- **Pre-commit**: Automated checks on commit

### Code Style
- Line length: 100 characters
- Follow numpy-style docstrings
- Use type hints consistently
- Target Python 3.10+

## Dependency Management

- **Package Manager**: `uv`
- **Runtime Dependencies**: Defined in `pyproject.toml` `[project.dependencies]`
- **Development Dependencies**: Defined in `[project.optional-dependencies.dev]`

### Adding Dependencies
```bash
# Add runtime dependency
uv add {package}

# Add development dependency  
uv add --dev {package}

# Upgrade all dependencies
uv sync --upgrade
```

## Key Technologies

- **FastAPI**: Web framework
- **Pydantic**: Data validation and serialization
- **SQLModel/SQLAlchemy**: Database ORM
- **HTMX**: Frontend interactivity
- **Jinja2**: Template engine
- **Tailwind CSS**: Styling (built via Docker)
- **Playwright**: End-to-end testing

## Submission Requirements
# Add development dependency  
Before submitting changes, ensure:

1. ✅ All tests pass (`poe test`)
2. ✅ Code is free of linting errors (`poe lint`)  
3. ✅ Logic is correct and robust
4. ✅ No regressions introduced
5. ✅ New tests added for new features/fixes
6. ✅ Documentation updated where necessary
7. ✅ Code follows project style guidelines

### Commit Standards
- Follow [Conventional Commits](https://www.conventionalcommits.org/) specification
- Use `cz bump` for version management
- Clear, descriptive commit messages

## AI Agent Specific Rules

When working as an AI agent on this project:

- **Persona**: Act as a Python Principal Engineer specializing in FastAPI, Pydantic, and SQLModel
- **Ownership**: Take full responsibility for understanding problems and delivering production-ready solutions
- **Communication**: Keep users informed of progress, ask clarifying questions when needed
- **Pragmatism**: Use expert judgment while following these guidelines
- **No Shortcuts**: Never commit code that breaks existing tests or leaves commented-out code
- **Scope**: Do not make changes outside the assigned task without explicit approval


## MCP Integration Guidelines

As an AI agent, you have access to Model Context Protocol (MCP) servers that provide additional capabilities beyond standard tools. You must check for available integrations and use them appropriately.

### Available MCP Integrations

#### Fetch MCP Server (`mcp_docker-mcp_fetch`)

**Capabilities:**
- Fetch content from URLs
- Extract content as markdown
- Access up-to-date information from the internet

**When to Use:**
- To gather current information about technologies, APIs, or documentation
- When you need to check external resources or documentation
- For research purposes during development

**Usage Pattern:**
```python
# Example: Fetch documentation
mcp_docker-mcp_fetch(
    url="https://fastapi.tiangolo.com/tutorial/",
    max_length=5000
)
```

#### Browser MCP Server (`mcp_docker-mcp_browser_*`)

**Capabilities:**
- Web page navigation, interaction, and testing
- Screenshot and accessibility snapshot capture
- Form filling, clicking, typing
- JavaScript evaluation
- Network request monitoring

**When to Use:**
- For end-to-end testing of web interfaces
- When debugging UI issues that require browser interaction
- To validate web application functionality
- For automated browser-based testing scenarios

**Usage Pattern:**
```python
# Example: Navigate and test a page
mcp_docker-mcp_browser_navigate(url="http://localhost:8000/admin")
mcp_docker-mcp_browser_snapshot()  # Better than screenshots for actions
mcp_docker-mcp_browser_click(element="Login button", ref="button_ref")
```

### Integration Discovery Process

**Before starting any task, you must:**

1. **Assess Available Integrations**: Review the functions available in your current session
2. **Match Capabilities to Task**: Determine which integrations could assist with your specific task
3. **Plan Integration Usage**: Incorporate appropriate MCP tools into your development plan
4. **Validate Integration Appropriateness**: Ensure the integration aligns with project goals and constraints

### Integration Best Practices

#### Research Integration

**When encountering unfamiliar technologies:**
1. Use fetch MCP to access current documentation
2. Verify API compatibility and best practices
3. Research security implications of new dependencies
4. Debug HTML pages in case Browser MCP has issues


####  Browser Testing Integration
**For UI-related tasks:**
1. Use browser MCP for end-to-end validation
2. Capture accessibility snapshots, not just screenshots
3. Validate functionality from the user's perspective
4. Test responsive design and cross-browser compatibility


### Integration Safety Guidelines

**Security Considerations:**
- Never expose sensitive information through MCP calls
- Validate external content before incorporating into code
- Be cautious with browser automation on production systems
- Review security analysis results before implementing suggestions

**Performance Considerations:**
- Use MCP integrations judiciously to avoid unnecessary overhead
- Cache results when appropriate to avoid redundant calls
- Prefer targeted analysis over broad scans when possible

### Integration Workflow Example

```
1. Task Assignment → Check available MCP integrations
2. Plan Development → Incorporate relevant MCP tools
3. Before Coding → Run code analysis on existing code
4. During Development → Use TDD guidance and security scanning
5. After Implementation → Run test coverage analysis
6. UI Testing → Use browser MCP for end-to-end validation
7. Final Review → Security analysis and pattern compliance
```

### Reporting Integration Usage

When using MCP integrations, you must:
- Document which integrations were used and why
- Report any significant findings from analysis tools
- Include integration results in your development summary
- Recommend follow-up actions based on integration insights
