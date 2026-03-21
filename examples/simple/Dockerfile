FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ ./src/
COPY examples/simple/ ./examples/simple/

# Install the project and dependencies
RUN uv sync --all-extras

# Expose the port
EXPOSE 8000

# Run the app
CMD ["uv", "run", "fastapi", "dev", "examples/simple/main.py", "--host", "0.0.0.0"]
