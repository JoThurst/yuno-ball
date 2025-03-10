#!/bin/bash
# YunoBall Master Script
# This script provides a unified interface for all YunoBall management scripts

# Configuration variables - modify these as needed
SCRIPTS_DIR="./scripts"

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
    echo -e "${BLUE}YunoBall Management Script${NC}"
    echo ""
    echo -e "${BLUE}Usage:${NC} $0 [command] [subcommand]"
    echo ""
    echo "Commands:"
    echo "  deploy      Deploy the YunoBall application"
    echo "  update      Update the YunoBall application"
    echo "  app         Manage the YunoBall application (start, stop, restart, status, logs)"
    echo "  ingest      Run data ingestion tasks (daily, full)"
    echo "  cron        Set up cron jobs for automated data ingestion"
    echo "  help        Display this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy                  # Deploy the application"
    echo "  $0 update                  # Update the application"
    echo "  $0 app start               # Start the application"
    echo "  $0 app stop                # Stop the application"
    echo "  $0 app restart             # Restart the application"
    echo "  $0 app status              # Check the application status"
    echo "  $0 app logs                # View the application logs"
    echo "  $0 ingest daily            # Run daily data ingestion"
    echo "  $0 ingest full             # Run full data ingestion"
    echo "  $0 cron                    # Set up cron jobs"
    echo ""
    exit 1
}

# Check if a command was provided
if [ $# -eq 0 ]; then
    usage
fi

# Check if the scripts directory exists
if [ ! -d "$SCRIPTS_DIR" ]; then
    print_error "Scripts directory not found: $SCRIPTS_DIR"
    exit 1
fi

# Process commands
case "$1" in
    deploy)
        print_message "Deploying YunoBall application..."
        $SCRIPTS_DIR/deploy.sh
        ;;
    update)
        print_message "Updating YunoBall application..."
        $SCRIPTS_DIR/update.sh
        ;;
    app)
        if [ $# -lt 2 ]; then
            print_error "Missing subcommand for 'app'"
            echo "Available subcommands: start, stop, restart, status, logs, nginx-logs"
            exit 1
        fi
        print_message "Managing YunoBall application..."
        $SCRIPTS_DIR/manage.sh "$2"
        ;;
    ingest)
        if [ $# -lt 2 ]; then
            print_error "Missing subcommand for 'ingest'"
            echo "Available subcommands: daily, full"
            exit 1
        fi
        print_message "Running data ingestion..."
        $SCRIPTS_DIR/ingest.sh "$2"
        ;;
    cron)
        print_message "Setting up cron jobs..."
        $SCRIPTS_DIR/setup_cron.sh
        ;;
    help)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        ;;
esac

exit 0 