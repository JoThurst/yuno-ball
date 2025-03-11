#!/bin/bash
# Setup Clean Virtual Environment for Python 3.12 Compatibility
# This script creates a clean virtual environment with a compatible version of setuptools

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

# Path to clean virtual environment - use absolute path
CLEAN_VENV="/home/ubuntu/clean_venv"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Check if clean virtual environment exists
if [ -d "$CLEAN_VENV" ]; then
    print_warning "Clean virtual environment already exists at $CLEAN_VENV"
    read -p "Do you want to recreate it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_message "Removing existing virtual environment..."
        rm -rf $CLEAN_VENV
    else
        print_message "Using existing virtual environment."
        exit 0
    fi
fi

# Create clean virtual environment
print_message "Creating clean virtual environment at $CLEAN_VENV..."
python3 -m venv $CLEAN_VENV

# Activate virtual environment
source $CLEAN_VENV/bin/activate

# Upgrade pip and install compatible setuptools
print_message "Upgrading pip and installing compatible setuptools..."
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir setuptools>=68.0.0

# Check if requirements.txt exists
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
else
    print_warning "requirements.txt not found in project root. Searching for it..."
    REQUIREMENTS_FILE=$(find "$PROJECT_ROOT" -name "requirements.txt" -type f | head -n 1)
    
    if [ -z "$REQUIREMENTS_FILE" ]; then
        print_error "Could not find requirements.txt in the project."
        print_message "Creating a basic requirements.txt file..."
        cat > "$PROJECT_ROOT/requirements.txt" << EOF
Flask==2.3.3
gunicorn==23.0.0
redis==5.0.1
psycopg2-binary==2.9.9
requests==2.31.0
EOF
        REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
    else
        print_message "Found requirements.txt at $REQUIREMENTS_FILE"
    fi
fi

# Install project dependencies
print_message "Installing project dependencies from $REQUIREMENTS_FILE..."
pip install --no-cache-dir -r "$REQUIREMENTS_FILE" || {
    print_warning "Error installing with standard method, trying alternative approach..."
    grep -v "^#" "$REQUIREMENTS_FILE" | sed 's/;.*$//' | sed 's/--hash=.*$//' > "$PROJECT_ROOT/requirements_no_hash.txt"
    pip install --no-cache-dir -r "$PROJECT_ROOT/requirements_no_hash.txt"
}

# Install additional packages that might be needed
print_message "Installing additional packages..."
pip install --no-cache-dir gunicorn

print_message "Clean virtual environment setup complete!"
print_message "To use this environment with yunoball.sh, run:"
print_message "  ./scripts/run_with_clean_venv.sh [options] [command] [subcommand]"

exit 0 