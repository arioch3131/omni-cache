#!/bin/bash

# This script runs integration tests for the redis adapter.

# --- Configuration ---
set -e
set -u
set -o pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$PROJECT_ROOT/src/omni_cache/adapters/redis/"
TEST_DIR="$PROJECT_ROOT/tests/integration/adapters/redis/"
COVERAGE_THRESHOLD=80

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
    echo -e "${COLOR_RED}ERROR: Not in a Python virtual environment. Please activate one before running this script.${COLOR_NC}\n"
    exit 1
fi

REQUIRED_COMMANDS=("pytest" "pytest-cov")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command_exists "$cmd"; then
        echo -e "${COLOR_RED}ERROR: Command '$cmd' not found.${COLOR_NC}\n"
        echo "Please install the development dependencies, for example by running:"
        echo "pip install -e '.[dev]'"
        exit 1
    fi
done

# --- Main Execution ---
cd "$PROJECT_ROOT"

print_header "Running Integration Tests for redis Adapter"
echo "Running pytest with coverage for $SOURCE_DIR..."
pytest "$TEST_DIR" --cov="$SOURCE_DIR" --cov-fail-under=$COVERAGE_THRESHOLD --cov-report=term-missing

print_header "redis Adapter Integration Tests Passed Successfully!"
echo -e "${COLOR_GREEN}Code coverage for redis adapter is above ${COVERAGE_THRESHOLD}%.${COLOR_NC}"

exit 0
