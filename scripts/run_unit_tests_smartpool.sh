#!/bin/bash

# This script runs unit tests for the smartpool adapter.

# --- Configuration ---
set -e
set -u
set -o pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$PROJECT_ROOT/src/omni_cache/adapters/smartpool/"
TEST_DIR="$PROJECT_ROOT/tests/unit/adapters/smartpool/"
COVERAGE_THRESHOLD=95

# --- Output Colors ---
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_RED='\033[0;31m'
COLOR_NC='\033[0m' # No Color

# --- Helper Functions ---
print_header() {
    echo -e "\n${COLOR_YELLOW}=======================================================================${COLOR_NC}"
    echo -e "${COLOR_YELLOW}  $1${COLOR_NC}"
    echo -e "${COLOR_YELLOW}=======================================================================${COLOR_NC}"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Pre-flight Checks ---
if ! [[ "${VIRTUAL_ENV:-}" ]]; then
    echo -e "${COLOR_RED}ERROR: Not in a Python virtual environment. Please activate one before running this script.${COLOR_NC}"
    exit 1
fi

# Verify that all required development tools are installed.
REQUIRED_COMMANDS=("mypy" "bandit" "pytest")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command_exists "$cmd"; then
        echo -e "${COLOR_RED}ERROR: Command '$cmd' not found.${COLOR_NC}"
        echo "Please install the development dependencies, for example by running:"
        echo "pip install -e '.[dev]'"
        exit 1
    fi
done

# --- Main Execution ---

# Change to the project root directory to ensure all paths are resolved correctly.
cd "$PROJECT_ROOT"

# Install core development dependencies
print_header "Installing Core Dependencies"
pip install -e ".[dev]"

# --- Static Analysis ---
print_header "Running Static Analysis Tools"
echo "Running mypy for static type checking..."
mypy "$SOURCE_DIR"

echo "Running bandit for security vulnerability scanning..."
bandit -r "$SOURCE_DIR" -s B311

# --- Testing ---
print_header "Running Automated Tests for Core"
echo "Running pytest and generating a code coverage report..."
pytest "$TEST_DIR" --cov="$SOURCE_DIR" --cov-fail-under="$COVERAGE_THRESHOLD"


# --- Success ---
print_header "All core tests passed successfully!"
echo -e "${COLOR_GREEN}Great job! Your core code is clean, secure, and thoroughly tested.${COLOR_NC}"

exit 0

