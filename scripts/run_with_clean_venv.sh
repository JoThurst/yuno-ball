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

# Path to clean virtual environment - use absolute path
CLEAN_VENV="/home/ubuntu/clean_venv"

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

# Pass through SSL-related environment variables if they exist
if [ ! -z "${CERT_EMAIL}" ]; then
    export CERT_EMAIL="${CERT_EMAIL}"
    print_message "Using provided SSL certificate email: ${CERT_EMAIL}"
fi

# Pass through AWS configuration if provided
for var in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_REGION FORCE_LOCAL; do
    if [ ! -z "${!var}" ]; then
        export "$var=${!var}"
        if [ "$var" = "AWS_SECRET_ACCESS_KEY" ]; then
            print_message "$var is set"
        else
            print_message "Using $var: ${!var}"
        fi
    fi
done

# Pass through email configuration if provided
for var in SMTP_SERVER SMTP_PORT SMTP_USERNAME SMTP_PASSWORD FROM_EMAIL BASE_URL; do
    if [ ! -z "${!var}" ]; then
        export "$var=${!var}"
        if [ "$var" = "SMTP_PASSWORD" ]; then
            print_message "$var is set"
        else
            print_message "Using $var: ${!var}"
        fi
    fi
done

# Check for --local flag and set FORCE_LOCAL
if [[ " $@ " =~ " --local " ]]; then
    export FORCE_LOCAL=true
    print_message "Running in local mode - CloudWatch disabled"
else
    export FORCE_LOCAL=false
    print_message "Running with CloudWatch enabled"
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the yunoball.sh script with the provided arguments
print_message "Running yunoball.sh with clean virtual environment..."
if [ -f "$SCRIPT_DIR/yunoball.sh" ]; then
    "$SCRIPT_DIR/yunoball.sh" "$@"
else
    print_error "yunoball.sh not found in $SCRIPT_DIR"
    print_error "Make sure you're running this script from the scripts directory"
    exit 1
fi

exit $? 