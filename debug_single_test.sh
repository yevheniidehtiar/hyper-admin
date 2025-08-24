#!/bin/bash

set -e

echo "--- Running single test for Python 3.10 with highest resolution ---"
log_file="logs/debug_py3.10_highest.log"

# Run the test commands and redirect output to log file
{
  echo "--- Running: uv venv ---"
  uv venv

  echo "--- Running: uv sync --all-extras ---"
  uv sync --all-extras

  echo "--- Running: uv run pytest tests/test_basic.py tests/test_import.py ---"
  uv run pytest tests/test_basic.py tests/test_import.py

} > "$log_file" 2>&1 || true # continue even if a command fails

echo "--- Single test finished ---"
