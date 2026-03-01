#!/bin/bash

# This script runs a series of code formatters and linters to ensure code quality.

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
SOURCE_DIR="$PROJECT_ROOT/src/"
TESTS_DIR="$PROJECT_ROOT/tests"

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
REQUIRED_COMMANDS=("black" "isort" "flake8" "pylint")
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

# --- Code Formatting ---
print_header "Running Code Formatters"
echo "Checking code formatting with black..."
black "$SOURCE_DIR" "$TESTS_DIR"
echo "Verifying import sorting with isort..."
isort "$SOURCE_DIR" "$TESTS_DIR"

# --- Linting ---
print_header "Running Linters"
echo "Running flake8 for style guide enforcement..."
flake8 "$SOURCE_DIR"
echo "Running pylint for in-depth code analysis..."
pylint "$SOURCE_DIR"

# --- Success ---
print_header "All formatters and linters passed successfully!"
echo -e "${COLOR_GREEN}Great job! Your code is clean and well-formatted.${COLOR_NC}"

exit 0
