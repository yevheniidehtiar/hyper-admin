#!/bin/bash

set -e

PYTHON_VERSIONS=("3.8" "3.9" "3.10" "3.11" "3.12" "3.13")
RESOLUTION_STRATEGIES=("highest" "lowest-direct" "lowest")

mkdir -p logs

for py_version in "${PYTHON_VERSIONS[@]}"; do
  for resolution in "${RESOLUTION_STRATEGIES[@]}"; do
    echo "--- Running tests for Python $py_version with $resolution resolution ---"
    log_file="logs/py${py_version}_${resolution}.log"

    # Run the test commands and redirect output to log file
    {
      echo "--- Running: uv sync --no-cache --python $py_version --resolution $resolution ---"
      # Removed --all-extras as per user instruction
      uv sync --no-cache --python "$py_version" --resolution "$resolution"

      # If sync was successful, the virtual env is active and contains the dependencies.
      # We can now run linting and tests.

      # Activate the virtual environment to make `pytest` available.
      # The venv is created by `uv sync` in `.venv`.
      source .venv/bin/activate

      echo "--- Running: PYTEST_ADDOPTS=\"\" pytest ---"
      # Clear addopts to avoid issues with missing pytest-cov
      PYTEST_ADDOPTS="" pytest

    } > "$log_file" 2>&1 || true # continue even if a command fails

    echo "--- Finished tests for Python $py_version with $resolution resolution ---"
    echo ""
  done
done

echo "--- All tests finished ---"
