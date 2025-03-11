#!/bin/bash
# YunoBall Data Ingestion Script
# This script runs data ingestion tasks for the YunoBall application

# Configuration variables - modify these as needed
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
CLEAN_VENV="/home/ubuntu/clean_venv"  # Path to clean virtual environment

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

# Display usage information if no command is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  daily       Run daily data ingestion"
    echo "  full        Run full data ingestion (takes longer)"
    echo ""
    exit 1
fi

# Process commands
case "$1" in
    daily)
        print_message "Running daily data ingestion..."
        cd $APP_DIR
        source "$CLEAN_VENV/bin/activate"
        python daily_ingest.py
        print_message "Daily data ingestion completed."
        ;;
    full)
        print_message "Running full data ingestion (this may take a while)..."
        cd $APP_DIR
        source "$CLEAN_VENV/bin/activate"
        python ingest_data.py
        print_message "Full data ingestion completed."
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  daily       Run daily data ingestion"
        echo "  full        Run full data ingestion (takes longer)"
        echo ""
        exit 1
        ;;
esac

exit 0 