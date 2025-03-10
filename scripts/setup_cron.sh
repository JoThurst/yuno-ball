#!/bin/bash
# YunoBall Cron Setup Script
# This script sets up cron jobs for automated data ingestion

set -e  # Exit on error

# Configuration variables - modify these as needed
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
SCRIPTS_DIR="$APP_DIR/scripts"

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
echo "          YunoBall Cron Setup Script"
echo "=========================================================="
echo ""
echo "This script will set up cron jobs for automated data ingestion."
echo ""
echo "Application directory: $APP_DIR"
echo ""
echo "Press ENTER to continue or CTRL+C to abort..."
read

# Create a log directory if it doesn't exist
print_message "Creating log directory..."
mkdir -p $APP_DIR/logs

# Create a wrapper script for the daily ingestion
print_message "Creating daily ingestion wrapper script..."
cat > $SCRIPTS_DIR/daily_ingest_wrapper.sh << EOF
#!/bin/bash
# Wrapper script for daily ingestion

# Set environment variables
export FORCE_PROXY=true

# Change to the application directory
cd $APP_DIR

# Run the daily ingestion script with proxy support
$APP_DIR/venv/bin/python $APP_DIR/daily_ingest.py --proxy > $APP_DIR/logs/daily_ingest_\$(date +\%Y\%m\%d).log 2>&1

# Exit with the script's exit code
exit \$?
EOF

# Make the wrapper script executable
chmod +x $SCRIPTS_DIR/daily_ingest_wrapper.sh

# Create a wrapper script for the weekly ingestion
print_message "Creating weekly ingestion wrapper script..."
cat > $SCRIPTS_DIR/weekly_ingest_wrapper.sh << EOF
#!/bin/bash
# Wrapper script for weekly ingestion

# Set environment variables
export FORCE_PROXY=true

# Change to the application directory
cd $APP_DIR

# Run the full ingestion script with proxy support
$APP_DIR/venv/bin/python $APP_DIR/ingest_data.py --proxy > $APP_DIR/logs/weekly_ingest_\$(date +\%Y\%m\%d).log 2>&1

# Exit with the script's exit code
exit \$?
EOF

# Make the wrapper script executable
chmod +x $SCRIPTS_DIR/weekly_ingest_wrapper.sh

# Set up the cron jobs
print_message "Setting up cron jobs..."

# Create a temporary file for the crontab
TEMP_CRONTAB=$(mktemp)

# Get the current crontab
crontab -l > $TEMP_CRONTAB 2>/dev/null || true

# Add the daily ingestion job (runs at 4:00 AM every day)
echo "# YunoBall daily data ingestion - runs at 4:00 AM every day" >> $TEMP_CRONTAB
echo "0 4 * * * $SCRIPTS_DIR/daily_ingest_wrapper.sh" >> $TEMP_CRONTAB

# Add the weekly ingestion job (runs at 2:00 AM every Sunday)
echo "# YunoBall weekly data ingestion - runs at 2:00 AM every Sunday" >> $TEMP_CRONTAB
echo "0 2 * * 0 $SCRIPTS_DIR/weekly_ingest_wrapper.sh" >> $TEMP_CRONTAB

# Install the new crontab
crontab $TEMP_CRONTAB

# Remove the temporary file
rm $TEMP_CRONTAB

# Final message
print_message "Cron jobs set up successfully!"
echo ""
echo "The following cron jobs have been set up:"
echo "  - Daily ingestion: Runs at 4:00 AM every day"
echo "  - Weekly ingestion: Runs at 2:00 AM every Sunday"
echo ""
echo "Logs will be saved to $APP_DIR/logs/"
echo ""
echo "To view the current cron jobs:"
echo "  crontab -l"
echo ""
echo "To edit the cron jobs:"
echo "  crontab -e"
echo ""
echo "==========================================================" 