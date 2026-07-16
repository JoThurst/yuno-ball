#!/bin/bash
# Script to Modify Deployment Scripts for Clean Virtual Environment
# This script modifies existing deployment scripts to use the clean virtual environment

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

# Path to scripts directory
SCRIPTS_DIR="."

# Path to clean virtual environment
CLEAN_VENV=~/clean_venv

# Check if clean virtual environment exists
if [ ! -d "$CLEAN_VENV" ]; then
    print_error "Clean virtual environment not found at $CLEAN_VENV"
    print_error "Please run ../setup_clean_venv.sh first"
    exit 1
fi

# Backup original scripts
print_message "Backing up original scripts..."
mkdir -p backup
cp deploy.sh backup/deploy.sh.bak
cp update.sh backup/update.sh.bak
cp manage.sh backup/manage.sh.bak
cp ingest.sh backup/ingest.sh.bak
cp setup_cron.sh backup/setup_cron.sh.bak

# Modify deploy.sh
print_message "Modifying deploy.sh..."
sed -i 's|python3 -m venv "\$APP_DIR/venv"|# Using clean virtual environment instead of creating a new one|g' deploy.sh
sed -i 's|source "\$APP_DIR/venv/bin/activate"|VENV_PATH="'"$CLEAN_VENV"'"\nsource "\$VENV_PATH/bin/activate"|g' deploy.sh
sed -i 's|ExecStart=\$APP_DIR/venv/bin/gunicorn|ExecStart='"$CLEAN_VENV"'/bin/gunicorn|g' deploy.sh

# Modify update.sh
print_message "Modifying update.sh..."
sed -i 's|source "\$APP_DIR/venv/bin/activate"|VENV_PATH="'"$CLEAN_VENV"'"\nsource "\$VENV_PATH/bin/activate"|g' update.sh

# Modify manage.sh
print_message "Modifying manage.sh..."
sed -i 's|source "\$APP_DIR/venv/bin/activate"|VENV_PATH="'"$CLEAN_VENV"'"\nsource "\$VENV_PATH/bin/activate"|g' manage.sh

# Modify ingest.sh
print_message "Modifying ingest.sh..."
sed -i 's|source "\$APP_DIR/venv/bin/activate"|VENV_PATH="'"$CLEAN_VENV"'"\nsource "\$VENV_PATH/bin/activate"|g' ingest.sh

# Modify setup_cron.sh
print_message "Modifying setup_cron.sh..."
sed -i 's|source "\$APP_DIR/venv/bin/activate"|VENV_PATH="'"$CLEAN_VENV"'"\nsource "\$VENV_PATH/bin/activate"|g' setup_cron.sh
sed -i 's|"\$APP_DIR/venv/bin/python|"'"$CLEAN_VENV"'/bin/python|g' setup_cron.sh

print_message "All scripts have been modified to use the clean virtual environment at $CLEAN_VENV"
print_message "Original scripts have been backed up to backup/"

exit 0 