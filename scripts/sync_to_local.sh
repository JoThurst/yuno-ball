#!/bin/bash
# Script to sync documentation and scripts to local repository
# Usage: ./sync_to_local.sh /path/to/local/repository

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if local repository path is provided
if [ -z "$1" ]; then
    print_error "Local repository path not provided"
    print_message "Usage: ./sync_to_local.sh /path/to/local/repository"
    exit 1
fi

LOCAL_REPO="$1"

# Check if local repository exists
if [ ! -d "$LOCAL_REPO" ]; then
    print_error "Local repository not found at $LOCAL_REPO"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Create scripts directory in local repository if it doesn't exist
if [ ! -d "$LOCAL_REPO/scripts" ]; then
    print_message "Creating scripts directory in local repository..."
    mkdir -p "$LOCAL_REPO/scripts"
fi

# Copy documentation
print_message "Copying documentation to local repository..."
cp "$PROJECT_ROOT/DEVELOPER.md" "$LOCAL_REPO/"

# Copy scripts
print_message "Copying scripts to local repository..."
cp "$SCRIPT_DIR/setup_clean_venv.sh" "$LOCAL_REPO/scripts/"
cp "$SCRIPT_DIR/run_with_clean_venv.sh" "$LOCAL_REPO/scripts/"
cp "$SCRIPT_DIR/setup_production.sh" "$LOCAL_REPO/scripts/"
cp "$SCRIPT_DIR/sync_to_local.sh" "$LOCAL_REPO/scripts/"

# Copy WSGI template
print_message "Copying WSGI template to local repository..."
cp "$PROJECT_ROOT/wsgi.py.template" "$LOCAL_REPO/"

# Make scripts executable in local repository
print_message "Making scripts executable in local repository..."
chmod +x "$LOCAL_REPO/scripts/"*.sh

print_message "Sync complete!"
print_message "Files copied to $LOCAL_REPO:"
print_message "  - DEVELOPER.md"
print_message "  - wsgi.py.template"
print_message "  - scripts/setup_clean_venv.sh"
print_message "  - scripts/run_with_clean_venv.sh"
print_message "  - scripts/setup_production.sh"
print_message "  - scripts/sync_to_local.sh"

exit 0 