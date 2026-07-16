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
pip cache purge
pip install --no-cache-dir --upgrade pip
pip uninstall -y setuptools
pip install --no-cache-dir --force-reinstall setuptools==65.5.1

# Check if requirements.txt exists
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
else
    print_warning "requirements.txt not found in project root. Creating basic file..."
    cat > "$PROJECT_ROOT/requirements.txt" << EOF
Flask==2.3.3
gunicorn==23.0.0
redis==5.0.1
psycopg2-binary==2.9.9
requests==2.31.0
boto3==1.34.0
python-dotenv==1.0.0
botocore==1.34.0
EOF
    REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
fi

# Install project dependencies with no cache
print_message "Installing project dependencies from $REQUIREMENTS_FILE..."
export PYTHONNOUSERSITE=1  # Prevent reading from user site-packages

# First install Flask-Mail separately without dependencies
print_message "Installing Flask-Mail separately..."
pip install --no-cache-dir --no-deps --ignore-installed Flask-Mail==0.9.1

# Then install remaining dependencies
pip install --no-cache-dir --ignore-installed -r "$REQUIREMENTS_FILE" || {
    print_warning "Error installing with standard method, trying alternative approach..."
    grep -v "^#" "$REQUIREMENTS_FILE" | sed 's/;.*$//' | sed 's/--hash=.*$//' > "$PROJECT_ROOT/requirements_no_hash.txt"
    pip install --no-cache-dir --ignore-installed -r "$PROJECT_ROOT/requirements_no_hash.txt"
}

# Verify Flask-Mail installation
python -c "import flask_mail" || {
    print_warning "Flask-Mail verification failed, attempting reinstall..."
    pip uninstall -y Flask-Mail
    pip install --no-cache-dir Flask-Mail==0.9.1
}

# Check if .env file exists and create from example if it doesn't
if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
    print_warning "No .env file found. Creating from .env.example..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    print_message "Please update the .env file with your configuration values."
fi

print_message "Clean virtual environment setup complete!"
print_message "Next steps:"
print_message "1. Update your .env file with your configuration"
print_message "2. Run the application using:"
print_message "   ./scripts/run_with_clean_venv.sh [options] [command] [subcommand]"

exit 0 