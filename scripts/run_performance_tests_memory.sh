#!/bin/bash

# This script runs performance tests for the memory adapter.

# --- Configuration ---
set -e
set -u
set -o pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_DIR="$PROJECT_ROOT/tests/performance/adapters/memory/"

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

REQUIRED_COMMANDS=("pytest")
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

print_header "Running Performance Tests for memory Adapter"
echo "Running pytest for $TEST_DIR..."
pytest "$TEST_DIR"

print_header "memory Adapter Performance Tests Completed Successfully!"
echo -e "${COLOR_GREEN}All performance tests for memory adapter ran without errors.${COLOR_NC}"

exit 0
