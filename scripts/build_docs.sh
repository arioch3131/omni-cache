#!/bin/bash

# This script builds the Sphinx documentation for the project.

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
DOCS_DIR="$PROJECT_ROOT/docs"

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

# --- Pre-flight Checks ---

# Ensure the script is run from within a Python virtual environment.
if ! [[ "${VIRTUAL_ENV:-}" ]]; then
    echo -e "${COLOR_RED}ERROR: Not in a Python virtual environment. Please activate one before running this script.${COLOR_NC}"
    exit 1
fi

# --- Main Execution ---

# Change to the project root directory to ensure all paths are resolved correctly.
cd "$PROJECT_ROOT"

# --- Build Documentation ---
print_header "Building Sphinx Documentation"

# Check if 'sphinx' is installed, and install it if not.
if ! python -m sphinx --version >/dev/null 2>&1; then
    echo "Sphinx is not installed. Installing it now..."
    pip install sphinx sphinx-rtd-theme
fi

# Build the documentation.
echo "Building the documentation..."
sphinx-build -b html "$DOCS_DIR" "$DOCS_DIR/_build/html"

# --- Success ---
print_header "Documentation built successfully!"
echo -e "${COLOR_GREEN}The documentation can be found in the 'docs/_build/html' directory.${COLOR_NC}"

exit 0
