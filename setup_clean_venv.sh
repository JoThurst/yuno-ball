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

# Path to clean virtual environment
CLEAN_VENV=~/clean_venv

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

# Install project dependencies
print_message "Installing project dependencies..."
pip install --no-cache-dir -r requirements.txt || {
    print_warning "Error installing with standard method, trying alternative approach..."
    grep -v "^#" requirements.txt | sed 's/;.*$//' | sed 's/--hash=.*$//' > requirements_no_hash.txt
    pip install --no-cache-dir -r requirements_no_hash.txt
}

print_message "Clean virtual environment setup complete!"
print_message "To use this environment with yunoball.sh, run:"
print_message "  ./run_with_clean_venv.sh [options] [command] [subcommand]"

exit 0 