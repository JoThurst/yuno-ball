#!/bin/bash
# YunoBall Management Script
# This script provides commands to manage the YunoBall application

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

# Display usage information if no command is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start           Start the YunoBall application with proxy support"
    echo "  start-no-proxy  Start the YunoBall application without proxy support"
    echo "  stop            Stop the YunoBall application"
    echo "  restart         Restart the YunoBall application with proxy support"
    echo "  restart-no-proxy Restart the YunoBall application without proxy support"
    echo "  status          Check the status of the YunoBall application"
    echo "  logs            View the application logs"
    echo "  nginx-logs      View the Nginx logs"
    echo ""
    exit 1
fi

# Process commands
case "$1" in
    start)
        print_message "Starting YunoBall application with proxy support..."
        # Set environment variables for proxy support
        systemctl set-environment FORCE_PROXY=true
        systemctl set-environment FORCE_LOCAL=false
        systemctl start $APP_NAME
        print_message "YunoBall application started with proxy support."
        ;;
    start-no-proxy)
        print_message "Starting YunoBall application without proxy support..."
        # Set environment variables to disable proxy
        systemctl set-environment FORCE_PROXY=false
        systemctl set-environment FORCE_LOCAL=true
        systemctl start $APP_NAME
        print_message "YunoBall application started without proxy support."
        ;;
    stop)
        print_message "Stopping YunoBall application..."
        systemctl stop $APP_NAME
        print_message "YunoBall application stopped."
        ;;
    restart)
        print_message "Restarting YunoBall application with proxy support..."
        # Set environment variables for proxy support
        systemctl set-environment FORCE_PROXY=true
        systemctl set-environment FORCE_LOCAL=false
        systemctl restart $APP_NAME
        print_message "YunoBall application restarted with proxy support."
        ;;
    restart-no-proxy)
        print_message "Restarting YunoBall application without proxy support..."
        # Set environment variables to disable proxy
        systemctl set-environment FORCE_PROXY=false
        systemctl set-environment FORCE_LOCAL=true
        systemctl restart $APP_NAME
        print_message "YunoBall application restarted without proxy support."
        ;;
    status)
        print_message "Checking YunoBall application status..."
        systemctl status $APP_NAME
        ;;
    logs)
        print_message "Viewing YunoBall application logs..."
        journalctl -u $APP_NAME -f
        ;;
    nginx-logs)
        print_message "Viewing Nginx logs..."
        tail -f /var/log/nginx/$APP_NAME.*.log
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start           Start the YunoBall application with proxy support"
        echo "  start-no-proxy  Start the YunoBall application without proxy support"
        echo "  stop            Stop the YunoBall application"
        echo "  restart         Restart the YunoBall application with proxy support"
        echo "  restart-no-proxy Restart the YunoBall application without proxy support"
        echo "  status          Check the status of the YunoBall application"
        echo "  logs            View the application logs"
        echo "  nginx-logs      View the Nginx logs"
        echo ""
        exit 1
        ;;
esac

exit 0 