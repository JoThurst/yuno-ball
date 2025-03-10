#!/bin/bash
# YunoBall Data Ingestion Script
# This script runs data ingestion tasks for the YunoBall application

set -e  # Exit on error

# Configuration variables - modify these as needed
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
VENV_DIR="$APP_DIR/venv"

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

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root or with sudo"
    exit 1
fi

# Display usage information
usage() {
    echo -e "${BLUE}Usage:${NC} $0 [command]"
    echo ""
    echo "Commands:"
    echo "  daily       Run daily data ingestion tasks"
    echo "  full        Run full data ingestion (one-time/weekly tasks)"
    echo "  help        Display this help message"
    echo ""
    exit 1
}

# Check if a command was provided
if [ $# -eq 0 ]; then
    usage
fi

# Function to run a Python script with the virtual environment
run_python_script() {
    cd $APP_DIR
    source $VENV_DIR/bin/activate
    
    # Set proxy environment variable
    export FORCE_PROXY=true
    
    # Run the script
    python "$1" --proxy
    
    # Check exit status
    if [ $? -eq 0 ]; then
        print_message "Script $1 completed successfully."
    else
        print_error "Script $1 failed with exit code $?."
    fi
}

# Process commands
case "$1" in
    daily)
        print_message "Running daily data ingestion tasks..."
        run_python_script "daily_ingest.py"
        ;;
    full)
        print_message "Running full data ingestion tasks..."
        run_python_script "ingest_data.py"
        ;;
    help)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        ;;
esac

print_message "Data ingestion completed."
exit 0 