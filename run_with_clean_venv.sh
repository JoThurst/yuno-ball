#!/bin/bash
# Wrapper Script for yunoball.sh
# This script runs yunoball.sh with the clean virtual environment

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

# Path to clean virtual environment
CLEAN_VENV=~/clean_venv

# Check if clean virtual environment exists
if [ ! -d "$CLEAN_VENV" ]; then
    print_error "Clean virtual environment not found at $CLEAN_VENV"
    print_error "Please run ./setup_clean_venv.sh first"
    exit 1
fi

# Export environment variables for child processes
export VIRTUAL_ENV=$CLEAN_VENV
export PATH="$VIRTUAL_ENV/bin:$PATH"
export PIP_NO_CACHE_DIR=1

# Run the yunoball.sh script with the provided arguments
print_message "Running yunoball.sh with clean virtual environment..."
./yunoball.sh "$@"

exit $? 