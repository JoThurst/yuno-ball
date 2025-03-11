#!/bin/bash
# YunoBall Update Script
# This script updates the YunoBall application

# Configuration variables - modify these as needed
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
CLEAN_VENV="/home/ubuntu/clean_venv"  # Path to clean virtual environment
BRANCH_NAME=${GIT_BRANCH:-"developProxy"}  # Use environment variable or default to developProxy

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

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root or with sudo"
    exit 1
fi

# Check if clean virtual environment exists
if [ ! -d "$CLEAN_VENV" ]; then
    print_error "Clean virtual environment not found at $CLEAN_VENV"
    print_error "Please run ./setup_clean_venv.sh first"
    exit 1
fi

# Check if application directory exists
if [ ! -d "$APP_DIR" ]; then
    print_error "Application directory not found: $APP_DIR"
    print_error "Please run deploy.sh first"
    exit 1
fi

# Display update message
print_message "Updating YunoBall application..."
print_message "Branch: $BRANCH_NAME"
print_message "Application directory: $APP_DIR"
print_message "Using clean virtual environment: $CLEAN_VENV"

# Update repository
print_message "Updating repository..."
cd $APP_DIR
git fetch
git checkout $BRANCH_NAME
git pull origin $BRANCH_NAME

# Use the clean virtual environment
print_message "Using clean virtual environment..."
source "$CLEAN_VENV/bin/activate"

# Update dependencies
print_message "Updating Python dependencies..."
pip install --no-cache-dir -r requirements.txt || {
    print_warning "Error installing with standard method, trying alternative approach..."
    grep -v "^#" requirements.txt | sed 's/;.*$//' | sed 's/--hash=.*$//' > requirements_no_hash.txt
    pip install --no-cache-dir -r requirements_no_hash.txt
}

# Restart the application
print_message "Restarting the application..."
systemctl restart $APP_NAME

print_message "YunoBall application has been updated successfully!"
print_message "Branch: $BRANCH_NAME"

# Final message
echo ""
echo "To check the status of your application:"
echo "  sudo systemctl status $APP_NAME.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u $APP_NAME.service -f"
echo ""
echo "==========================================================" 