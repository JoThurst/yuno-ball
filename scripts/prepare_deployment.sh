#!/bin/bash
# Prepare system for fresh deployment
# This script handles stopping the existing service and preparing for a new deployment

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

# Check if running as root/sudo
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Stop the existing service
print_message "Stopping yunoball service..."
systemctl stop yunoball.service || {
    print_warning "Failed to stop service, might not exist yet"
}

# Disable the service to prevent auto-start
print_message "Disabling yunoball service..."
systemctl disable yunoball.service 2>/dev/null || {
    print_warning "Failed to disable service, might not exist yet"
}

# Backup existing service file if it exists
if [ -f "/etc/systemd/system/yunoball.service" ]; then
    print_message "Backing up existing service file..."
    mv /etc/systemd/system/yunoball.service /etc/systemd/system/yunoball.service.bak
fi

# Install Node.js and npm if not already installed
print_message "Checking Node.js and npm installation..."
if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
    print_message "Installing Node.js and npm..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# Setup logging directory and permissions
print_message "Setting up logging directory..."
mkdir -p /var/www/yunoball/logs
touch /var/www/yunoball/logs/nba_data_module.log
chown -R ubuntu:ubuntu /var/www/yunoball/logs
chmod -R 755 /var/www/yunoball/logs
chmod 664 /var/www/yunoball/logs/nba_data_module.log

# Build static assets
print_message "Installing npm dependencies..."
cd /var/www/yunoball
npm install

print_message "Cleaning up old static assets..."
rm -f /var/www/yunoball/app/static/css/output.css
rm -f /var/www/yunoball/app/static/dist/*.js

print_message "Building static assets (CSS and JS)..."
# Force rebuild CSS in the correct location
print_message "Building CSS..."
npx tailwindcss -i ./app/static/css/tailwind.css -o ./app/static/css/output.css --minify

# Verify the CSS was built
if [ ! -f "/var/www/yunoball/app/static/css/output.css" ]; then
    print_error "CSS build failed in production directory!"
    exit 1
fi

print_message "Building JS..."
npm run build:js

# Ensure static directories exist and have correct permissions
print_message "Setting up static directories..."
mkdir -p /var/www/yunoball/app/static/dist
mkdir -p /var/www/yunoball/app/static/css
chown -R ubuntu:ubuntu /var/www/yunoball/app/static
chmod -R 755 /var/www/yunoball/app/static

# Add timestamp to CSS file for cache busting
TIMESTAMP=$(date +%s)
sed -i "1i /* Build: $TIMESTAMP */" /var/www/yunoball/app/static/css/output.css

# Clear Nginx cache if it exists
if [ -d "/var/cache/nginx" ]; then
    print_message "Clearing Nginx cache..."
    rm -rf /var/cache/nginx/*
fi

# Verify the final CSS file
print_message "Verifying CSS build..."
if [ -f "/var/www/yunoball/app/static/css/output.css" ]; then
    print_message "CSS build successful!"
    ls -l /var/www/yunoball/app/static/css/output.css
    head -n 5 /var/www/yunoball/app/static/css/output.css
else
    print_error "CSS file not found in production directory!"
    exit 1
fi

# Create new service file
print_message "Creating new service file..."
cat > /etc/systemd/system/yunoball.service << EOF
[Unit]
Description=YunoBall Flask Application
After=network.target redis-server.service
Requires=redis-server.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/yunoball
Environment="PATH=/home/ubuntu/clean_venv/bin"
Environment="FLASK_ENV=production"
Environment="FORCE_PROXY=true"
Environment="PROXY_ENABLED=true"
Environment="FORCE_LOCAL=false"
Environment="LOG_FILE=/var/www/yunoball/logs/nba_data_module.log"
ExecStart=/home/ubuntu/clean_venv/bin/uvicorn wsgi:app --host 127.0.0.1 --port 8000 --log-level debug
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd to recognize new service file
print_message "Reloading systemd daemon..."
systemctl daemon-reload

# Clean up old virtual environment
if [ -d "/home/ubuntu/clean_venv" ]; then
    print_message "Removing old virtual environment..."
    rm -rf /home/ubuntu/clean_venv
fi

# Clean up old deployment files (optional, uncomment if needed)
# print_message "Cleaning up old deployment files..."
# rm -rf /var/www/yunoball/*

print_message "System prepared for fresh deployment!"
print_message "Next steps:"
print_message "1. Run setup_clean_venv.sh to create new environment"
print_message "2. Update .env file with production configuration"
print_message "3. Start the service with: sudo systemctl start yunoball"
print_message "4. Check status with: sudo systemctl status yunoball"

exit 0 