#!/bin/bash

set -e

PYTHON_VERSIONS=("3.8" "3.9" "3.10" "3.11" "3.12" "3.13")
RESOLUTION_STRATEGIES=("highest" "lowest-direct" "lowest")

# Create a file to store the report
REPORT_FILE="TEST_MATRIX_REPORT.md"
echo "# Python Version Compatibility Matrix" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| Python Version | Resolution Strategy | Status |" >> "$REPORT_FILE"
echo "|----------------|---------------------|--------|" >> "$REPORT_FILE"

for python_version in "${PYTHON_VERSIONS[@]}"; do
  for resolution in "${RESOLUTION_STRATEGIES[@]}"; do
    echo "================================================================================"
    echo "Testing with Python $python_version and resolution strategy $resolution"
    echo "================================================================================"

    LOG_FILE="test_log_${python_version}_${resolution}.log"

    # The `script` command will capture all output, including stderr
    script -q -c "
      set -e
      # Create a virtual environment with the specified Python version
      uv venv --python \"$python_version\" .venv
      # Activate the virtual environment
      source .venv/bin/activate
      # Install dependencies
      uv sync --resolution \"$resolution\"
      # Run linting and tests
      poe lint
      poe test:unit
    " "$LOG_FILE"

    # Check the exit code of the script command
    if [ $? -eq 0 ]; then
      STATUS="✅ Pass"
      echo "| $python_version | $resolution | $STATUS |" >> "$REPORT_FILE"
      rm "$LOG_FILE" # Clean up log file on success
    else
      STATUS="❌ Fail"
      echo "| $python_version | $resolution | $STATUS |" >> "$REPORT_FILE"
      echo "" >> "$REPORT_FILE"
      echo "### 🪵 Logs for Python $python_version with $resolution resolution" >> "$REPORT_FILE"
      echo "" >> "$REPORT_FILE"
      echo '```' >> "$REPORT_FILE"
      cat "$LOG_FILE" >> "$REPORT_FILE"
      echo '```' >> "$REPORT_FILE"
      echo "" >> "$REPORT_FILE"
      rm "$LOG_FILE" # Clean up log file after appending
    fi

    # Deactivate and remove the virtual environment
    # The subshell from `script` will handle deactivation, but we still need to remove the directory
    rm -rf .venv

    # Clean up temporary Python downloads
    rm -rf /home/jules/.local/share/uv/python/.temp

    echo "================================================================================"
    echo "Finished testing with Python $python_version and resolution strategy $resolution. Status: $STATUS"
    echo "================================================================================"
  done
done

echo "Test matrix execution complete. Report generated at $REPORT_FILE"
