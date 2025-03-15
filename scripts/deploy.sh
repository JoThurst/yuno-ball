#!/bin/bash
# YunoBall Deployment Script
# This script automates the deployment of the YunoBall application on Ubuntu

set -e  # Exit on error

# Configuration variables - modify these as needed
APP_NAME="yunoball"
DOMAIN="yunoball.xyz"
APP_DIR="/var/www/$APP_NAME"
CLEAN_VENV="/home/ubuntu/clean_venv"  # Path to clean virtual environment
REPO_URL="https://github.com/JoThurst/nba-sports-analytics.git"
BRANCH_NAME=${GIT_BRANCH:-"developProxy"}  # Use environment variable or default to developProxy
NGINX_CONF="/etc/nginx/sites-available/$APP_NAME.conf"
USER=$(whoami)
EMAIL=${CERT_EMAIL:-""}  # For Let's Encrypt - must be provided via environment variable

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
echo "          YunoBall Deployment Script"
echo "=========================================================="
echo ""
echo "This script will set up the YunoBall application on your server."
echo "It will install all necessary dependencies, configure Nginx,"
echo "set up SSL certificates, and create a systemd service."
echo ""
echo "Domain: $DOMAIN"
echo "Application directory: $APP_DIR"
echo "Git branch: $BRANCH_NAME"
echo "Using clean virtual environment: $CLEAN_VENV"
echo ""
echo "Press ENTER to continue or CTRL+C to abort..."
read

# Update system packages
print_message "Updating system packages..."
apt update && apt upgrade -y

# Install required packages
print_message "Installing required packages..."
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx redis-server git ufw fail2ban

# Create application directory
print_message "Creating application directory..."
mkdir -p $APP_DIR
chown -R $USER:$USER $APP_DIR

# Clone repository
print_message "Cloning repository from branch $BRANCH_NAME..."
if [ -d "$APP_DIR/.git" ]; then
    print_warning "Git repository already exists. Pulling latest changes from branch $BRANCH_NAME..."
    cd $APP_DIR
    git fetch
    git checkout $BRANCH_NAME
    git pull origin $BRANCH_NAME
else
    git clone -b $BRANCH_NAME $REPO_URL $APP_DIR
    cd $APP_DIR
fi

# Make all scripts executable
print_message "Making deployment scripts executable..."
chmod +x $APP_DIR/scripts/*.sh
chown $USER:$USER $APP_DIR/scripts/*.sh

# Verify script permissions
print_message "Verifying script permissions..."
if [ ! -x "$APP_DIR/scripts/prepare_deployment.sh" ] || [ ! -x "$APP_DIR/scripts/setup_clean_venv.sh" ]; then
    print_error "Failed to set script permissions. Please check the scripts directory."
    exit 1
fi

# Prepare for fresh deployment
print_message "Preparing for fresh deployment..."
./scripts/prepare_deployment.sh

# Set up clean virtual environment
print_message "Setting up clean virtual environment..."
./scripts/setup_clean_venv.sh

# Create .env file if it doesn't exist
if [ ! -f "$APP_DIR/.env" ]; then
    print_message "Creating .env file..."
    cat > "$APP_DIR/.env" << EOF
# Database Configuration
DATABASE_URL=${DATABASE_URL:-postgresql://user:password@localhost:5432/yunoball}

# API Configuration
API_KEY=${API_KEY:-$(openssl rand -hex 32)}

# JWT Configuration
JWT_SECRET_KEY=${JWT_SECRET_KEY:-$(openssl rand -hex 32)}
JWT_EXPIRATION_DAYS=1

# Application Security
SECRET_KEY=${SECRET_KEY:-$(openssl rand -hex 32)}

# AWS Configuration (for CloudWatch monitoring)
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-}
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ROLE_ARN=${AWS_ROLE_ARN:-}

# Email Configuration
SMTP_SERVER=${SMTP_SERVER:-smtp.gmail.com}
SMTP_PORT=${SMTP_PORT:-587}
SMTP_USERNAME=${SMTP_USERNAME:-}
SMTP_PASSWORD=${SMTP_PASSWORD:-}
FROM_EMAIL=${FROM_EMAIL:-noreply@$DOMAIN}

# Application Configuration
FLASK_ENV=production
BASE_URL=https://$DOMAIN

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Monitoring Configuration
LOCAL_MONITORING=false
EOF
    chmod 600 "$APP_DIR/.env"
    chown $USER:$USER "$APP_DIR/.env"
fi

# Create temporary HTTP-only Nginx configuration
print_message "Creating temporary HTTP Nginx configuration..."
cat > $NGINX_CONF << EOF
# $DOMAIN Nginx Configuration - Temporary HTTP version

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;

    # Root directory for static files
    root $APP_DIR;

    # Logs
    access_log /var/log/nginx/$APP_NAME.access.log;
    error_log /var/log/nginx/$APP_NAME.error.log;

    # Proxy settings for Flask application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files
    location /static/ {
        alias $APP_DIR/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}
EOF

# Enable and start Redis
print_message "Enabling and starting Redis..."
systemctl enable redis-server
systemctl restart redis-server

# Enable Nginx site
print_message "Enabling Nginx site..."
ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default  # Remove default site if it exists
nginx -t  # Test configuration
systemctl restart nginx

# Start the application service
print_message "Starting the application service..."
systemctl daemon-reload
systemctl enable $APP_NAME.service
systemctl start $APP_NAME.service

# Set up SSL with Let's Encrypt (only if domain is properly configured)
print_message "Checking if domain is properly configured for SSL..."
if [ -z "$EMAIL" ]; then
    print_error "No email address provided for SSL certificate. Please set CERT_EMAIL environment variable."
    print_message "Example: CERT_EMAIL=your@email.com sudo ./deploy.sh"
    exit 1
fi

if host $DOMAIN > /dev/null 2>&1; then
    print_message "Domain $DOMAIN is properly configured. Setting up SSL with Let's Encrypt..."
    certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --redirect --email $EMAIL || {
        print_error "Failed to obtain SSL certificates."
        print_error "Please check:"
        print_error "1. Domain DNS is properly configured"
        print_error "2. Port 80 and 443 are open"
        print_error "3. Email address is valid"
        exit 1
    }
else
    print_warning "Domain $DOMAIN is not properly configured yet. Skipping SSL setup."
    print_warning "Once DNS is configured, run: sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --redirect --email $EMAIL"
fi

# Configure firewall
print_message "Configuring firewall..."
ufw allow 'Nginx Full'
ufw allow ssh
ufw --force enable

# Set up fail2ban
print_message "Setting up fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# Initialize the database tables
print_message "Initializing database tables..."
cd $APP_DIR
source $CLEAN_VENV/bin/activate
export FLASK_APP=run.py
flask db init-users || print_warning "Failed to initialize users table. You may need to run this manually."

# Set up CloudWatch resources if AWS credentials are configured
if [ ! -z "$AWS_ACCESS_KEY_ID" ] && [ ! -z "$AWS_SECRET_ACCESS_KEY" ]; then
    print_message "Setting up CloudWatch resources..."
    python setup_dashboard.py
    python setup_alarms.py
fi

# Final message
print_message "Deployment completed successfully!"
echo ""
echo "Your YunoBall application is now running at http://$DOMAIN"
if host $DOMAIN > /dev/null 2>&1 && [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "HTTPS is enabled. You can also access it at: https://$DOMAIN"
fi
echo "Using Git branch: $BRANCH_NAME"
echo ""
echo "Important environment variables have been set in: $APP_DIR/.env"
echo "Please review and update any sensitive values."
echo ""
echo "To check the status of your application:"
echo "  sudo systemctl status $APP_NAME.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u $APP_NAME.service -f"
echo ""
echo "To restart the application:"
echo "  sudo systemctl restart $APP_NAME.service"
echo ""
echo "==========================================================" 