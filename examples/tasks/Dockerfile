FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ ./src/
# First-party plugins are uv workspace members (pyproject [tool.uv.workspace]); `uv sync` fails
# without them.
COPY plugins/ ./plugins/
COPY examples/__init__.py ./examples/__init__.py
COPY examples/tasks/ ./examples/tasks/

# `--all-packages` also installs the workspace plugins' extras, which brings in pgtask
# (hyperadmin-tasks[pgtask]) next to psycopg.
RUN uv sync --all-extras --all-packages

EXPOSE 8000

# One process: the pgtask worker runs inside it (run_worker in main.py), so keep one uvicorn worker.
CMD ["uv", "run", "uvicorn", "examples.tasks.main:app", "--host", "0.0.0.0", "--port", "8000"]
