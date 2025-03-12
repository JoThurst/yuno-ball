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
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
USER=$(whoami)
EMAIL=${CERT_EMAIL:-""}  # For Let's Encrypt - must be provided via environment variable

# JWT and App secrets
JWT_SECRET_KEY=${JWT_SECRET_KEY:-$(openssl rand -hex 32)}  # Generate random key if not provided
SECRET_KEY=${SECRET_KEY:-$(openssl rand -hex 32)}  # Generate random key if not provided
API_KEY=${API_KEY:-$(openssl rand -hex 32)}  # Generate random key if not provided

# Email Configuration
SMTP_SERVER=${SMTP_SERVER:-"smtp.gmail.com"}
SMTP_PORT=${SMTP_PORT:-"587"}
SMTP_USERNAME=${SMTP_USERNAME:-""}  # Must be provided via environment variable
SMTP_PASSWORD=${SMTP_PASSWORD:-""}  # Must be provided via environment variable
FROM_EMAIL=${FROM_EMAIL:-"noreply@yunoball.xyz"}
BASE_URL=${BASE_URL:-"https://yunoball.xyz"}

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

# Check if clean virtual environment exists
if [ ! -d "$CLEAN_VENV" ]; then
    print_error "Clean virtual environment not found at $CLEAN_VENV"
    print_error "Please run ./setup_clean_venv.sh first"
    exit 1
fi

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

# Use the clean virtual environment
print_message "Using clean virtual environment..."
source "$CLEAN_VENV/bin/activate"

# Install dependencies
print_message "Installing Python dependencies..."
pip install --no-cache-dir -r $APP_DIR/requirements.txt || {
    print_warning "Error installing with standard method, trying alternative approach..."
    grep -v "^#" $APP_DIR/requirements.txt | sed 's/;.*$//' | sed 's/--hash=.*$//' > $APP_DIR/requirements_no_hash.txt
    pip install --no-cache-dir -r $APP_DIR/requirements_no_hash.txt
}
pip install --no-cache-dir gunicorn  # For production serving

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

# Create systemd service file
print_message "Creating systemd service..."
cat > $SERVICE_FILE << EOF
[Unit]
Description=YunoBall Flask Application
After=network.target redis-server.service

[Service]
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$CLEAN_VENV/bin"
Environment="PROXY_ENABLED=true"
Environment="FLASK_ENV=production"
Environment="JWT_SECRET_KEY=$JWT_SECRET_KEY"
Environment="SECRET_KEY=$SECRET_KEY"
Environment="API_KEY=$API_KEY"
Environment="SMTP_SERVER=$SMTP_SERVER"
Environment="SMTP_PORT=$SMTP_PORT"
Environment="SMTP_USERNAME=$SMTP_USERNAME"
Environment="SMTP_PASSWORD=$SMTP_PASSWORD"
Environment="FROM_EMAIL=$FROM_EMAIL"
Environment="BASE_URL=$BASE_URL"
ExecStart=$CLEAN_VENV/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 'run:app'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
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

# Enable and start the application service
print_message "Enabling and starting the application service..."
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

# Check required environment variables
if [ -z "$SMTP_USERNAME" ] || [ -z "$SMTP_PASSWORD" ]; then
    print_error "Email configuration is incomplete. Please set SMTP_USERNAME and SMTP_PASSWORD environment variables."
    print_message "Example:"
    print_message "export SMTP_USERNAME=your-email@gmail.com"
    print_message "export SMTP_PASSWORD=your-app-specific-password"
    exit 1
fi

# After cloning repository and before starting the service, set up configuration
print_message "Setting up application configuration..."
if [ -f "$APP_DIR/app/config.example.py" ]; then
    if [ ! -f "$APP_DIR/app/config.py" ]; then
        cp "$APP_DIR/app/config.example.py" "$APP_DIR/app/config.py"
        # Update configuration values
        sed -i "s|postgresql://user:password@localhost:5432/database|$DATABASE_URL|g" "$APP_DIR/app/config.py"
        sed -i "s|your-api-key-here|$API_KEY|g" "$APP_DIR/app/config.py"
        sed -i "s|your-jwt-secret-key-here|$JWT_SECRET_KEY|g" "$APP_DIR/app/config.py"
        sed -i "s|your-secret-key-here|$SECRET_KEY|g" "$APP_DIR/app/config.py"
        sed -i "s|your-email@gmail.com|$SMTP_USERNAME|g" "$APP_DIR/app/config.py"
        sed -i "s|your-app-specific-password|$SMTP_PASSWORD|g" "$APP_DIR/app/config.py"
        sed -i "s|noreply@yourdomain.com|$FROM_EMAIL|g" "$APP_DIR/app/config.py"
        sed -i "s|http://localhost:5000|$BASE_URL|g" "$APP_DIR/app/config.py"
        chown $USER:$USER "$APP_DIR/app/config.py"
        chmod 600 "$APP_DIR/app/config.py"  # Restrict permissions
    else
        print_warning "Configuration file already exists. Skipping configuration setup."
    fi
else
    print_error "Configuration example file not found. Please check the repository."
    exit 1
fi

# Initialize the database tables
print_message "Initializing database tables..."
cd $APP_DIR
source $CLEAN_VENV/bin/activate
export FLASK_APP=run.py
flask db init-users || print_warning "Failed to initialize users table. You may need to run this manually."

# Final message
print_message "Deployment completed successfully!"
echo ""
echo "Your YunoBall application is now running at http://$DOMAIN"
if host $DOMAIN > /dev/null 2>&1 && [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo "HTTPS is enabled. You can also access it at: https://$DOMAIN"
fi
echo "Using Git branch: $BRANCH_NAME"
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