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
