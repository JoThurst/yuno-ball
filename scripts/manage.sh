#!/bin/bash
# YunoBall Management Script
# This script provides commands to manage the YunoBall application

# Configuration variables - modify these as needed
APP_NAME="yunoball"

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
    echo "  start           Start the YunoBall application with proxy support"
    echo "  start-no-proxy  Start the YunoBall application without proxy support"
    echo "  stop            Stop the YunoBall application"
    echo "  restart         Restart the YunoBall application with proxy support"
    echo "  restart-no-proxy Restart the YunoBall application without proxy support"
    echo "  status          Check the status of the YunoBall application"
    echo "  logs            View the application logs"
    echo "  nginx-logs      View the Nginx access and error logs"
    echo "  help            Display this help message"
    echo ""
    exit 1
}

# Check if a command was provided
if [ $# -eq 0 ]; then
    usage
fi

# Process commands
case "$1" in
    start)
        print_message "Starting YunoBall application with proxy support..."
        # Ensure proxy is enabled
        systemctl set-environment FORCE_PROXY=true
        systemctl set-environment FORCE_LOCAL=false
        systemctl start $APP_NAME.service
        systemctl status $APP_NAME.service
        ;;
    start-no-proxy)
        print_message "Starting YunoBall application without proxy support..."
        # Disable proxy for this session
        systemctl set-environment FORCE_LOCAL=true
        systemctl set-environment FORCE_PROXY=false
        systemctl start $APP_NAME.service
        systemctl status $APP_NAME.service
        ;;
    stop)
        print_message "Stopping YunoBall application..."
        systemctl stop $APP_NAME.service
        systemctl status $APP_NAME.service
        ;;
    restart)
        print_message "Restarting YunoBall application with proxy support..."
        # Ensure proxy is enabled
        systemctl set-environment FORCE_PROXY=true
        systemctl set-environment FORCE_LOCAL=false
        systemctl restart $APP_NAME.service
        systemctl status $APP_NAME.service
        ;;
    restart-no-proxy)
        print_message "Restarting YunoBall application without proxy support..."
        # Disable proxy for this session
        systemctl set-environment FORCE_LOCAL=true
        systemctl set-environment FORCE_PROXY=false
        systemctl restart $APP_NAME.service
        systemctl status $APP_NAME.service
        ;;
    status)
        print_message "Checking YunoBall application status..."
        systemctl status $APP_NAME.service
        ;;
    logs)
        print_message "Viewing YunoBall application logs..."
        journalctl -u $APP_NAME.service -f
        ;;
    nginx-logs)
        print_message "Viewing Nginx logs..."
        echo -e "${BLUE}Access Log:${NC}"
        tail -n 50 /var/log/nginx/$APP_NAME.access.log
        echo ""
        echo -e "${BLUE}Error Log:${NC}"
        tail -n 50 /var/log/nginx/$APP_NAME.error.log
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