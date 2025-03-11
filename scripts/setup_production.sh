#!/bin/bash
# Production Setup Script for YunoBall
# This script automates the setup process for a production deployment

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

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root or with sudo"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Configuration variables
APP_NAME="yunoball"
APP_DIR="/var/www/$APP_NAME"
DOMAIN=${1:-"yourdomain.com"}  # Default domain or use first argument
USER=${2:-"ubuntu"}            # Default user or use second argument

print_message "Setting up $APP_NAME production environment..."
print_message "Domain: $DOMAIN"
print_message "User: $USER"

# 1. Install required packages
print_message "Installing required packages..."
apt update
apt install -y python3-venv python3-dev build-essential libpq-dev postgresql postgresql-contrib nginx redis-server

# 2. Create application directory if it doesn't exist
if [ ! -d "$APP_DIR" ]; then
    print_message "Creating application directory at $APP_DIR..."
    mkdir -p $APP_DIR
    
    # Copy project files if running from the project directory
    if [ "$PROJECT_ROOT" != "$APP_DIR" ]; then
        print_message "Copying project files to $APP_DIR..."
        cp -r $PROJECT_ROOT/* $APP_DIR/
    fi
    
    # Set ownership
    chown -R $USER:$USER $APP_DIR
else
    print_warning "Application directory already exists at $APP_DIR"
fi

# 3. Create WSGI file if it doesn't exist
if [ ! -f "$APP_DIR/wsgi.py" ] && [ -f "$APP_DIR/wsgi.py.template" ]; then
    print_message "Creating WSGI file from template..."
    cp $APP_DIR/wsgi.py.template $APP_DIR/wsgi.py
    chown $USER:$USER $APP_DIR/wsgi.py
elif [ ! -f "$APP_DIR/wsgi.py" ]; then
    print_message "Creating WSGI file..."
    cat > $APP_DIR/wsgi.py << EOF
import os
import sys

# Add the application directory to the Python path
sys.path.insert(0, "$APP_DIR")

# Set environment variables for proxy configuration
os.environ["PROXY_ENABLED"] = "true"
os.environ["FORCE_PROXY"] = "true"

# Import the app
from app import create_app
application = create_app()

# For Gunicorn
app = application
EOF
    chown $USER:$USER $APP_DIR/wsgi.py
fi

# 4. Set up log file permissions
print_message "Setting up log file permissions..."
touch $APP_DIR/nba_data_module.log
chown $USER:$USER $APP_DIR/nba_data_module.log
chmod 664 $APP_DIR/nba_data_module.log

# 5. Create systemd service file
print_message "Creating systemd service file..."
cat > /etc/systemd/system/$APP_NAME.service << EOF
[Unit]
Description=YunoBall Flask Application
After=network.target redis-server.service
Requires=redis-server.service

[Service]
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=/home/$USER/clean_venv/bin"
Environment="PROXY_ENABLED=true"
Environment="FORCE_PROXY=true"
Environment="FLASK_ENV=production"
ExecStart=/home/$USER/clean_venv/bin/gunicorn --workers 1 --bind 127.0.0.1:8000 --log-level debug wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. Create Nginx configuration
print_message "Creating Nginx configuration..."
cat > /etc/nginx/sites-available/$APP_NAME << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
}
EOF

# Create symbolic link if it doesn't exist
if [ ! -f /etc/nginx/sites-enabled/$APP_NAME ]; then
    print_message "Enabling Nginx site..."
    ln -s /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
fi

# Test Nginx configuration
print_message "Testing Nginx configuration..."
nginx -t

# 7. Start and enable services
print_message "Starting and enabling services..."
systemctl start redis-server
systemctl enable redis-server
systemctl daemon-reload
systemctl start $APP_NAME.service
systemctl enable $APP_NAME.service
systemctl restart nginx

print_message "Production setup complete!"
print_message "You can check the status of the application with:"
print_message "  sudo systemctl status $APP_NAME.service"
print_message "You can view the logs with:"
print_message "  sudo journalctl -u $APP_NAME.service -f"
print_message "Your application should be accessible at: http://$DOMAIN"
print_message "To set up SSL, run:"
print_message "  sudo apt-get install certbot python3-certbot-nginx"
print_message "  sudo certbot --nginx -d $DOMAIN"

exit 0 