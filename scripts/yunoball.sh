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

# Display usage information
usage() {
    echo -e "${BLUE}YunoBall Management Script${NC}"
    echo ""
    echo -e "${BLUE}Usage:${NC} $0 [options] [command] [subcommand]"
    echo ""
    echo "Options:"
    echo "  --branch NAME     Specify a Git branch to use (default: $DEFAULT_BRANCH)"
    echo "  --no-proxy        Run without proxy support (for local development)"
    echo "  --smtp-server     SMTP server address (default: smtp.gmail.com)"
    echo "  --smtp-port       SMTP port (default: 587)"
    echo "  --smtp-user       SMTP username (required for email features)"
    echo "  --smtp-pass       SMTP password (required for email features)"
    echo "  --from-email     From email address (default: noreply@yunoball.xyz)"
    echo "  --base-url       Base URL for application (default: https://yunoball.xyz)"
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
    echo "  $0 --smtp-user user@gmail.com --smtp-pass mypass deploy  # Deploy with email config"
    echo "  $0 app start                        # Start the application with proxy support"
    echo "  $0 --no-proxy app start            # Start the application without proxy support"
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
    
    case "$arg" in
        --branch)
            i=$((i+1))
            if [ $i -le $# ]; then
                BRANCH="${!i}"
                print_message "Using branch: $BRANCH"
            else
                print_error "Missing branch name after --branch"
                exit 1
            fi
            ;;
        --no-proxy)
            USE_PROXY=false
            print_message "Running without proxy support"
            ;;
        --smtp-server)
            i=$((i+1))
            if [ $i -le $# ]; then
                export SMTP_SERVER="${!i}"
                print_message "Using SMTP server: $SMTP_SERVER"
            else
                print_error "Missing SMTP server after --smtp-server"
                exit 1
            fi
            ;;
        --smtp-port)
            i=$((i+1))
            if [ $i -le $# ]; then
                export SMTP_PORT="${!i}"
                print_message "Using SMTP port: $SMTP_PORT"
            else
                print_error "Missing port after --smtp-port"
                exit 1
            fi
            ;;
        --smtp-user)
            i=$((i+1))
            if [ $i -le $# ]; then
                export SMTP_USERNAME="${!i}"
                print_message "Using SMTP username: $SMTP_USERNAME"
            else
                print_error "Missing username after --smtp-user"
                exit 1
            fi
            ;;
        --smtp-pass)
            i=$((i+1))
            if [ $i -le $# ]; then
                export SMTP_PASSWORD="${!i}"
                print_message "SMTP password set"
            else
                print_error "Missing password after --smtp-pass"
                exit 1
            fi
            ;;
        --from-email)
            i=$((i+1))
            if [ $i -le $# ]; then
                export FROM_EMAIL="${!i}"
                print_message "Using from email: $FROM_EMAIL"
            else
                print_error "Missing email after --from-email"
                exit 1
            fi
            ;;
        --base-url)
            i=$((i+1))
            if [ $i -le $# ]; then
                export BASE_URL="${!i}"
                print_message "Using base URL: $BASE_URL"
            else
                print_error "Missing URL after --base-url"
                exit 1
            fi
            ;;
        *)
            ARGS+=("$arg")
            ;;
    esac
    
    i=$((i+1))
done

// ... existing code ... 