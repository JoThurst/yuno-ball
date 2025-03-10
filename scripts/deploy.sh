#!/bin/bash
# YunoBall Deployment Script
# This script automates the deployment of the YunoBall application on Ubuntu

set -e  # Exit on error

# Configuration variables - modify these as needed
APP_NAME="yunoball"
DOMAIN="yunoball.xyz"
APP_DIR="/var/www/$APP_NAME"
VENV_DIR="$APP_DIR/venv"
REPO_URL="https://github.com/yourusername/sports_analytics.git"  # Replace with your actual repo URL
NGINX_CONF="/etc/nginx/sites-available/$APP_NAME.conf"
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
USER=$(whoami)
EMAIL="your-email@example.com"  # For Let's Encrypt

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
print_message "Cloning repository..."
if [ -d "$APP_DIR/.git" ]; then
    print_warning "Git repository already exists. Pulling latest changes..."
    cd $APP_DIR
    git pull
else
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
fi

# Create virtual environment
print_message "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate

# Install dependencies
print_message "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # For production serving

# Create Nginx configuration
print_message "Creating Nginx configuration..."
cat > $NGINX_CONF << EOF
# $DOMAIN Nginx Configuration

# HTTP Server - Redirects to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;

    # Redirect all HTTP requests to HTTPS
    location / {
        return 301 https://\$host\$request_uri;
    }

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    # SSL Configuration - Certbot will update these
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/$DOMAIN/chain.pem;

    # SSL Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Other security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

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

    # Favicon
    location /favicon.ico {
        alias $APP_DIR/static/favicon.ico;
        access_log off;
        log_not_found off;
        expires max;
    }

    # Robots.txt
    location /robots.txt {
        alias $APP_DIR/static/robots.txt;
        access_log off;
        log_not_found off;
    }

    # Deny access to .htaccess files
    location ~ /\.ht {
        deny all;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
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
Environment="PATH=$VENV_DIR/bin"
Environment="PROXY_ENABLED=true"
Environment="FLASK_ENV=production"
ExecStart=$VENV_DIR/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 'run:app'
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
nginx -t  # Test configuration
systemctl restart nginx

# Set up SSL with Let's Encrypt
print_message "Setting up SSL with Let's Encrypt..."
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --email $EMAIL

# Configure firewall
print_message "Configuring firewall..."
ufw allow 'Nginx Full'
ufw allow ssh
ufw --force enable

# Enable and start the application service
print_message "Enabling and starting the application service..."
systemctl daemon-reload
systemctl enable $APP_NAME.service
systemctl start $APP_NAME.service

# Set up fail2ban
print_message "Setting up fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# Final message
print_message "Deployment completed successfully!"
echo ""
echo "Your YunoBall application is now running at https://$DOMAIN"
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