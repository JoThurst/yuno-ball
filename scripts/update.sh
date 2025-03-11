#!/bin/bash
# YunoBall Update Script
# This script updates the YunoBall application with the latest changes

set -e  # Exit on error

# Configuration variables - modify these as needed
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
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

# Display welcome message
clear
echo "=========================================================="
echo "          YunoBall Update Script"
echo "=========================================================="
echo ""
echo "This script will update the YunoBall application with the latest changes."
echo ""
echo "Application directory: $APP_DIR"
echo "Git branch: $BRANCH_NAME"
echo ""
echo "Press ENTER to continue or CTRL+C to abort..."
read

# Pull latest changes from repository
print_message "Pulling latest changes from branch $BRANCH_NAME..."
cd $APP_DIR
git fetch
git checkout $BRANCH_NAME
git pull origin $BRANCH_NAME

# Activate virtual environment
print_message "Activating virtual environment..."
source $VENV_DIR/bin/activate

# Update dependencies
print_message "Updating Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Restart the application service
print_message "Restarting the application service..."
systemctl restart $APP_NAME.service

# Final message
print_message "Update completed successfully!"
echo ""
echo "Your YunoBall application has been updated and restarted."
echo "Using Git branch: $BRANCH_NAME"
echo ""
echo "To check the status of your application:"
echo "  sudo systemctl status $APP_NAME.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u $APP_NAME.service -f"
echo ""
echo "==========================================================" 