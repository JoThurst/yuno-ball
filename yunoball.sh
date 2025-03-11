#!/bin/bash
# YunoBall Master Script
# This script provides a unified interface for all YunoBall management scripts

# Configuration variables - modify these as needed
SCRIPTS_DIR="./scripts"
DEFAULT_BRANCH="developProxy"  # Default branch to use

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
    echo -e "${BLUE}Usage:${NC} $0 [options] [command] [subcommand]"
    echo ""
    echo "Options:"
    echo "  --branch NAME  Specify a Git branch to use (default: $DEFAULT_BRANCH)"
    echo "  --no-proxy     Run without proxy support (for local development)"
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
    echo "  $0 deploy                           # Deploy using default branch"
    echo "  $0 --branch main deploy             # Deploy using main branch"
    echo "  $0 --branch developProxy update     # Update using developProxy branch"
    echo "  $0 app start                        # Start the application with proxy support"
    echo "  $0 --no-proxy app start             # Start the application without proxy support"
    echo "  $0 ingest daily                     # Run daily data ingestion"
    echo ""
    exit 1
}

# Parse options
BRANCH=$DEFAULT_BRANCH
USE_PROXY=true
ARGS=()

i=1
while [ $i -le $# ]; do
    arg="${!i}"
    
    if [ "$arg" == "--branch" ]; then
        i=$((i+1))
        if [ $i -le $# ]; then
            BRANCH="${!i}"
            print_message "Using branch: $BRANCH"
        else
            print_error "Missing branch name after --branch"
            exit 1
        fi
    elif [ "$arg" == "--no-proxy" ]; then
        USE_PROXY=false
        print_message "Running without proxy support"
    else
        ARGS+=("$arg")
    fi
    
    i=$((i+1))
done

# Set branch environment variable for child scripts
export GIT_BRANCH=$BRANCH

# Check if a command was provided
if [ ${#ARGS[@]} -eq 0 ]; then
    usage
fi

# Check if the scripts directory exists
if [ ! -d "$SCRIPTS_DIR" ]; then
    print_error "Scripts directory not found: $SCRIPTS_DIR"
    exit 1
fi

# Process commands
case "${ARGS[0]}" in
    deploy)
        print_message "Deploying YunoBall application (branch: $BRANCH)..."
        $SCRIPTS_DIR/deploy.sh
        ;;
    update)
        print_message "Updating YunoBall application (branch: $BRANCH)..."
        $SCRIPTS_DIR/update.sh
        ;;
    app)
        if [ ${#ARGS[@]} -lt 2 ]; then
            print_error "Missing subcommand for 'app'"
            echo "Available subcommands: start, stop, restart, status, logs, nginx-logs"
            exit 1
        fi
        
        # Handle proxy settings
        if [ "$USE_PROXY" = false ] && [ "${ARGS[1]}" = "start" ]; then
            print_message "Managing YunoBall application (without proxy)..."
            $SCRIPTS_DIR/manage.sh "start-no-proxy"
        elif [ "$USE_PROXY" = false ] && [ "${ARGS[1]}" = "restart" ]; then
            print_message "Managing YunoBall application (without proxy)..."
            $SCRIPTS_DIR/manage.sh "restart-no-proxy"
        else
            print_message "Managing YunoBall application..."
            $SCRIPTS_DIR/manage.sh "${ARGS[1]}"
        fi
        ;;
    ingest)
        if [ ${#ARGS[@]} -lt 2 ]; then
            print_error "Missing subcommand for 'ingest'"
            echo "Available subcommands: daily, full"
            exit 1
        fi
        print_message "Running data ingestion..."
        $SCRIPTS_DIR/ingest.sh "${ARGS[1]}"
        ;;
    cron)
        print_message "Setting up cron jobs..."
        $SCRIPTS_DIR/setup_cron.sh
        ;;
    help)
        usage
        ;;
    *)
        print_error "Unknown command: ${ARGS[0]}"
        usage
        ;;
esac

exit 0 