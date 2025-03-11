#!/bin/bash
# YunoBall Cron Setup Script
# This script sets up cron jobs for automated data ingestion
#
# ⚠️ WARNING: If running on AWS, be cautious about enabling automated ingestion.
# The multi-threaded ingestion process may exceed proxy rate limits.
# Consider running ingestion manually or with reduced concurrency.

# Configuration variables - modify these as needed
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
CLEAN_VENV="/home/ubuntu/clean_venv"  # Path to clean virtual environment
SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"

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

print_message "Setting up cron jobs for YunoBall data ingestion..."

# Create daily ingestion script
DAILY_SCRIPT="/etc/cron.daily/yunoball-daily-ingest"
cat > $DAILY_SCRIPT << EOF
#!/bin/bash
# YunoBall Daily Data Ingestion
cd $APP_DIR
source "$CLEAN_VENV/bin/activate"
python daily_ingest.py >> /var/log/yunoball-daily-ingest.log 2>&1
EOF
chmod +x $DAILY_SCRIPT

# Create weekly ingestion script
WEEKLY_SCRIPT="/etc/cron.weekly/yunoball-weekly-ingest"
cat > $WEEKLY_SCRIPT << EOF
#!/bin/bash
# YunoBall Weekly Data Ingestion
cd $APP_DIR
source "$CLEAN_VENV/bin/activate"
python ingest_data.py >> /var/log/yunoball-weekly-ingest.log 2>&1
EOF
chmod +x $WEEKLY_SCRIPT

print_message "Cron jobs have been set up successfully!"
print_message "Daily ingestion: $DAILY_SCRIPT"
print_message "Weekly ingestion: $WEEKLY_SCRIPT"

exit 0 