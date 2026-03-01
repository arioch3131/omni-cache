#!/bin/bash

# This script runs tests for the `examples` directory.

# --- Configuration ---
# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
set -u
# Return value of a pipeline is the value of the last command to exit with a non-zero status.
set -o pipefail

# Get the absolute path of the project's root directory.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EXAMPLES_DIR="$PROJECT_ROOT/examples"
EXAMPLES_TESTS_DIR="$PROJECT_ROOT/tests/examples"

# --- Output Colors ---
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_RED='\033[0;31m'
COLOR_NC='\033[0m' # No Color

# --- Helper Functions ---

# Prints a formatted header to the console.
# Arguments:
#   $1: The text to display in the header.
print_header() {
    echo -e "\n${COLOR_YELLOW}=======================================================================${COLOR_NC}"
    echo -e "${COLOR_YELLOW}  $1${COLOR_NC}"
    echo -e "${COLOR_YELLOW}=======================================================================${COLOR_NC}"
}

# Checks if a command exists in the current environment.
# Arguments:
#   $1: The name of the command to check.
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Pre-flight Checks ---

# Ensure the script is run from within a Python virtual environment.
if ! [[ "${VIRTUAL_ENV:-}" ]]; then
    echo -e "${COLOR_RED}ERROR: Not in a Python virtual environment. Please activate one before running this script.${COLOR_NC}"
    exit 1
fi

# Verify that all required development tools are installed.
REQUIRED_COMMANDS=("bandit" "pytest")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
    if ! command_exists "$cmd"; then
        echo -e "${COLOR_RED}ERROR: Command '$cmd' not found.${COLOR_NC}"
        echo "Please install the development dependencies, for example by running:"
        echo "pip install -e '.[dev,examples]'"
        exit 1
    fi
done

# --- Main Execution ---

# Change to the project root directory to ensure all paths are resolved correctly.
cd "$PROJECT_ROOT"

# Install example dependencies
print_header "Installing Example Dependencies"
pip install -e ".[dev,examples]"

# --- Security Analysis ---
print_header "Running Security Analysis for Examples"
echo "Running bandit for security vulnerability scanning..."
bandit -r "$EXAMPLES_DIR"

# --- Testing ---
print_header "Running Automated Tests for Examples"
echo "Running pytest for examples..."
pytest "$EXAMPLES_TESTS_DIR"

# --- Success ---
print_header "All example tests passed successfully!"
echo -e "${COLOR_GREEN}Great job! Your examples are secure and well-tested.${COLOR_NC}"

exit 0
