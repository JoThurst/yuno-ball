# YunoBall Developer Guide

This document provides comprehensive instructions for setting up, developing, and deploying the YunoBall application.

## Summary

YunoBall is a Flask-based web application for sports analytics, specifically focused on NBA data. This guide covers:

- Setting up a development environment with a clean Python virtual environment
- Deploying the application to a production server
- Managing static assets and database configuration
- Troubleshooting common issues
- Performing regular maintenance tasks

All scripts mentioned in this guide are located in the `scripts/` directory and should be made executable before use.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Production Deployment](#production-deployment)
4. [Authentication and Email Setup](#authentication-and-email-setup)
5. [Managing Static Assets](#managing-static-assets)
6. [Database Configuration](#database-configuration)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance](#maintenance)

## Prerequisites

- Ubuntu 20.04 or newer
- Python 3.12
- PostgreSQL
- Redis
- Node.js and npm (for frontend assets)
- Nginx (for production)

## Local Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd yunoball
```

### 2. Environment Configuration

1. Create a `.env` file based on the provided `.env.example`:
   ```bash
   cp .env.example .env
   ```

2. Configure your environment variables in `.env`:
   ```ini
   # Database Configuration
   DATABASE_URL=postgresql://user:password@host:5432/database?sslmode=require

   # API Configuration
   API_KEY=your_secure_api_key_here

   # JWT Configuration
   JWT_SECRET_KEY=your_jwt_secret_key_here
   JWT_EXPIRATION_DAYS=1

   # Application Security
   SECRET_KEY=your_flask_secret_key_here

   # AWS Configuration (for CloudWatch monitoring)
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_REGION=us-east-1
   AWS_ROLE_ARN=arn:aws:iam::<your-account-id>:role/CloudWatchMonitoringRole

   # Redis Configuration (for session/cache)
   REDIS_URL=redis://localhost:6379/0

   # Optional: Set to true to use local monitoring instead of CloudWatch
   LOCAL_MONITORING=true
   ```

3. Important Notes:
   - Never commit your `.env` file to version control
   - In production, set these variables in your AWS environment
   - For local development, `LOCAL_MONITORING=true` will disable CloudWatch integration

### 3. Make Scripts Executable

Before using any scripts, make them executable:

```bash
# Make all scripts in the scripts directory executable
chmod +x scripts/*.sh
```

### 4. Set Up a Clean Virtual Environment

We provide two scripts to help with environment setup:

- `setup_clean_venv.sh`: Creates a clean Python virtual environment
- `run_with_clean_venv.sh`: Runs commands using the clean virtual environment

```bash
# Create the clean virtual environment
./scripts/setup_clean_venv.sh

# Run commands with the clean environment
./scripts/run_with_clean_venv.sh --branch developProxy deploy
```

### 5. Database Configuration

The application now uses environment variables from `.env` for database configuration. The `db_config.py` file is included in the repository and does not need to be modified.

Key database configuration points:
- Connection parameters are read from the `DATABASE_URL` environment variable
- SSL mode is automatically enabled for Neon database connections
- Connection pooling is configured with optimal settings
- Automatic connection validation and recycling is implemented

For local development:
```bash
# Example DATABASE_URL format
DATABASE_URL=postgresql://user:password@localhost:5432/yunoball

# For Neon database
DATABASE_URL=postgresql://user:password@ep-xxxxx-xxxxx.region.aws.neon.tech/dbname?sslmode=require
```

For production:
- Set the `DATABASE_URL` in your AWS environment variables
- The application will automatically handle SSL and connection pooling

### 6. Database Backup and Maintenance

The application includes a DatabaseManager utility for handling backups and maintenance:

```python
from app.utils.database_manager import DatabaseManager

# Create an instance of the DatabaseManager
db_manager = DatabaseManager()

# Create different types of backups
db_manager.create_backup('daily')    # Daily backup
db_manager.create_backup('weekly')   # Weekly backup
db_manager.create_backup('monthly')  # Monthly backup

# Restore from a backup
db_manager.restore_backup('/path/to/backup.sql')

# Cleanup old backups (keep last 7 daily backups)
db_manager.cleanup_old_backups('daily', 7)
```

#### Backup Locations
- Windows: `%LOCALAPPDATA%\YunoBall\backups\`
- Linux: `/var/backup/yunoball/`

Each backup type has its own subdirectory:
- `daily/` - Daily incremental backups
- `weekly/` - Weekly full backups
- `monthly/` - Monthly archive backups
- `pre_migration/` - Backups before database migrations

#### Automated Backup Schedule
To set up automated backups:

1. Windows Task Scheduler:
```powershell
# Create a scheduled task for daily backups
schtasks /create /tn "YunoBall Daily Backup" /tr "python -c 'from app.utils.database_manager import DatabaseManager; DatabaseManager().create_backup(\"daily\")'" /sc daily /st 00:00
```

2. Linux Cron Jobs:
```bash
# Edit crontab
crontab -e

# Add backup schedules
0 0 * * * python3 -c 'from app.utils.database_manager import DatabaseManager; DatabaseManager().create_backup("daily")'   # Daily at midnight
0 0 * * 0 python3 -c 'from app.utils.database_manager import DatabaseManager; DatabaseManager().create_backup("weekly")'  # Weekly on Sunday
0 0 1 * * python3 -c 'from app.utils.database_manager import DatabaseManager; DatabaseManager().create_backup("monthly")' # Monthly on the 1st
```

#### Backup Verification and Maintenance
```python
# Verify backup integrity
is_valid = db_manager.verify_backup('/path/to/backup.sql')

# Clean up old backups
db_manager.cleanup_old_backups('daily', 7)    # Keep last 7 daily backups
db_manager.cleanup_old_backups('weekly', 4)   # Keep last 4 weekly backups
db_manager.cleanup_old_backups('monthly', 12)  # Keep last 12 monthly backups
```

### 4. Running the Application Locally

```bash
# Start Redis server
redis-server

# Run the Flask application
python run.py
```

The application will be available at http://localhost:8000

### 5. WSGI Template for Production

The repository includes a `wsgi.py.template` file that serves as a template for the WSGI entry point in production. This file is automatically used by the production setup script, but you can also use it manually:

```bash
# Copy the template to wsgi.py
cp wsgi.py.template wsgi.py

# Edit if necessary to adjust paths or settings
nano wsgi.py
```

The template includes:
- Python path configuration
- Environment variable setup for proxy support
- Application creation and export

This template ensures consistent WSGI configuration across different deployments.

## Production Deployment

### 1. Automated Setup (Recommended)

We provide an automated setup script that handles all the steps below. To use it:

```bash
# SSH into your server
ssh ubuntu@your-server-ip

# Clone the repository
git clone <repository-url>
cd yunoball

# Make scripts executable
chmod +x scripts/*.sh

# Set up SSL email for Let's Encrypt certificate
export CERT_EMAIL=your@email.com

# Run the production setup script with your domain and username
sudo -E ./scripts/setup_production.sh yourdomain.com ubuntu
```

The script will:
- Install all required packages
- Set up the application directory
- Create the WSGI entry point
- Configure log file permissions
- Create the systemd service
- Configure Nginx
- Set up SSL with Let's Encrypt (if CERT_EMAIL is provided)
- Start and enable all services

After running the script, you should be able to access your application at https://yourdomain.com.

### Environment Variables

The following environment variables are used by the deployment scripts:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| CERT_EMAIL | Email address for Let's Encrypt SSL certificates | Yes (for SSL) | None |
| GIT_BRANCH | Git branch to deploy | No | developProxy |
| FLASK_ENV | Flask environment | No | production |

To use these variables with the deployment scripts:

```bash
# Example with all variables set
export CERT_EMAIL=your@email.com
export GIT_BRANCH=main
sudo -E ./scripts/deploy.sh

# Or inline for a single command
CERT_EMAIL=your@email.com sudo -E ./scripts/deploy.sh
```

Note: The `-E` flag with sudo is important as it preserves the environment variables.

### Using with Clean Virtual Environment

When using the clean virtual environment setup, you can deploy with SSL using:

```bash
# Set up the clean virtual environment first
./scripts/setup_clean_venv.sh

# Deploy with SSL using run_with_clean_venv.sh
CERT_EMAIL=your@email.com sudo -E ./scripts/run_with_clean_venv.sh deploy
```

### 2. Manual Setup

If you prefer to set up the application manually, follow these steps:

#### 2.1. Server Preparation

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Install required packages
sudo apt install -y python3-venv python3-dev build-essential libpq-dev postgresql postgresql-contrib nginx redis-server
```

#### 2.2. Create a Clean Virtual Environment

```bash
# Create a clean virtual environment
python3 -m venv /home/ubuntu/clean_venv

# Activate the virtual environment
source /home/ubuntu/clean_venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install setuptools with a specific version to avoid hash issues
pip install setuptools==69.0.2

# Install dependencies
pip install -r requirements.txt

# Install Gunicorn
pip install gunicorn
```

#### 2.3. Application Setup

```bash
# Create application directory
sudo mkdir -p /var/www/yunoball

# Clone the repository
sudo git clone <repository-url> /var/www/yunoball

# Set proper ownership
sudo chown -R ubuntu:ubuntu /var/www/yunoball
```

#### 2.4. Create WSGI Entry Point

Create a file at `/var/www/yunoball/wsgi.py`:

```python
import os
import sys

# Add the application directory to the Python path
sys.path.insert(0, "/var/www/yunoball")

# Set environment variables for proxy configuration
os.environ["PROXY_ENABLED"] = "true"
os.environ["FORCE_PROXY"] = "true"

# Import the app
from app import create_app
application = create_app()

# For Gunicorn
app = application
```

#### 2.5. Set Up Log File Permissions

```bash
# Create the log file if it doesn't exist
sudo touch /var/www/yunoball/nba_data_module.log

# Set ownership to ubuntu user
sudo chown ubuntu:ubuntu /var/www/yunoball/nba_data_module.log

# Set permissions to allow reading and writing
sudo chmod 664 /var/www/yunoball/nba_data_module.log
```

#### 2.6. Create Systemd Service

Create a file at `/etc/systemd/system/yunoball.service`:

```
[Unit]
Description=YunoBall Flask Application
After=network.target redis-server.service
Requires=redis-server.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/yunoball
Environment="PATH=/home/ubuntu/clean_venv/bin"
Environment="PROXY_ENABLED=true"
Environment="FORCE_PROXY=true"
Environment="FLASK_ENV=production"
ExecStart=/home/ubuntu/clean_venv/bin/gunicorn --workers 1 --bind 127.0.0.1:8000 --log-level debug wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### 2.7. Configure Nginx

Create a file at `/etc/nginx/sites-available/yunoball`:

```
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/yunoball/static;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/yunoball /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

#### 2.8. Start and Enable Services

```bash
# Start and enable Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Start and enable the YunoBall service
sudo systemctl start yunoball.service
sudo systemctl enable yunoball.service
```

#### 2.9. Set Up SSL (Optional but Recommended)

SSL setup is automated in the deployment scripts when `CERT_EMAIL` is provided. To set up SSL manually:

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain and configure SSL certificate with automatic HTTP to HTTPS redirect
sudo certbot --nginx -d yourdomain.com --non-interactive --agree-tos --redirect --email your@email.com
```

To verify SSL certificate status:
```bash
# Check certificate status
sudo certbot certificates

# Test automatic renewal
sudo certbot renew --dry-run
```

SSL certificates from Let's Encrypt are valid for 90 days and will automatically renew via a systemd timer.

### Fresh Deployment

For a fresh deployment or to replace an existing deployment:

1. Automated Method (Recommended):
   ```bash
   # SSH into your server
   ssh ubuntu@your-server-ip

   # Clone the repository if not already present
   git clone <repository-url>
   cd yunoball

   # Make scripts executable
   chmod +x scripts/*.sh

   # Prepare for fresh deployment (stops existing service and cleans up)
   sudo ./scripts/prepare_deployment.sh

   # Set up clean environment
   ./scripts/setup_clean_venv.sh

   # Update .env with production values
   nano .env

   # Start the service
   sudo systemctl start yunoball
   ```

2. Manual Method:
   ```bash
   # Stop and disable existing service
   sudo systemctl stop yunoball
   sudo systemctl disable yunoball

   # Backup existing service file
   sudo mv /etc/systemd/system/yunoball.service /etc/systemd/system/yunoball.service.bak

   # Remove old virtual environment
   rm -rf /home/ubuntu/clean_venv

   # Create new service file
   sudo nano /etc/systemd/system/yunoball.service
   # Paste the service configuration (see below)

   # Reload systemd
   sudo systemctl daemon-reload

   # Set up new environment
   ./scripts/setup_clean_venv.sh

   # Update .env file
   nano .env

   # Start service
   sudo systemctl start yunoball
   ```

3. Service Configuration File (`/etc/systemd/system/yunoball.service`):
   ```ini
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
   ExecStart=/home/ubuntu/clean_venv/bin/gunicorn --workers 1 --bind 127.0.0.1:8000 --log-level debug wsgi:app
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

### Verifying Deployment

After deployment, verify the setup:

1. Check service status:
   ```bash
   sudo systemctl status yunoball
   ```

2. View logs:
   ```bash
   sudo journalctl -u yunoball -f
   ```

3. Test the application:
   ```bash
   curl http://localhost:8000/health
   ```

4. Verify CloudWatch metrics (if enabled):
   ```bash
   # Check CloudWatch logs
   aws logs describe-log-streams --log-group-name /aws/yunoball

   # View recent metrics
   aws cloudwatch get-metric-data --namespace NBA --metric-name APIResponseTime
   ```

### Troubleshooting Deployment

1. If service fails to start:
   ```bash
   # Check detailed service logs
   sudo journalctl -u yunoball -n 100 --no-pager

   # Verify permissions
   sudo chown -R ubuntu:ubuntu /var/www/yunoball
   sudo chmod -R 755 /var/www/yunoball
   ```

2. If environment issues occur:
   ```bash
   # Verify virtual environment
   ls -la /home/ubuntu/clean_venv/bin/python

   # Check Python path
   /home/ubuntu/clean_venv/bin/python -c "import sys; print(sys.path)"
   ```

3. If database connection fails:
   ```bash
   # Test database connection
   /home/ubuntu/clean_venv/bin/python -c "from db_config import init_db, get_db_connection; init_db('YOUR_DATABASE_URL'); conn = get_db_connection(); print('Connection successful')"
   ```

## Authentication and Email Setup

### Authentication System

The application uses JWT (JSON Web Token) based authentication with the following features:
- Password complexity requirements
- Rate limiting for login attempts
- Token refresh mechanism
- Admin and regular user roles
- Password reset functionality

#### User Management

Create an admin user:
```bash
export FLASK_APP=run.py
flask db init-users  # Initialize user tables
flask db create-admin  # Create admin user
```

### Email Configuration

The application supports email functionality, particularly for password resets. You can configure email settings in several ways:

1. Environment Variables:
```bash
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-specific-password"
export SMTP_SERVER="smtp.gmail.com"  # Optional, defaults to Gmail
export SMTP_PORT="587"               # Optional, defaults to 587
export FROM_EMAIL="noreply@yourdomain.com"
export BASE_URL="https://yourdomain.com"
```

2. Command Line Arguments (when deploying):
```bash
sudo ./scripts/yunoball.sh \
    --smtp-user your-email@gmail.com \
    --smtp-pass your-app-specific-password \
    --from-email noreply@yourdomain.com \
    --base-url https://yourdomain.com \
    deploy
```

#### Gmail Setup

If using Gmail for sending emails:

1. Enable 2-Factor Authentication in your Google Account
2. Generate an App Password:
   - Go to Google Account settings
   - Security
   - 2-Step Verification
   - App passwords
   - Generate a new app password for "Mail"
3. Use this app password as your SMTP_PASSWORD

#### Email Features

The system includes:
- Password reset emails with secure tokens
- HTML email templates
- Rate limiting for email requests
- Secure token storage using Redis
- Token expiration (1 hour for reset tokens)

#### Testing Email Configuration

To test your email setup:
```bash
# Set up environment variables
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-specific-password"

# Run the application with email support
./scripts/run_with_clean_venv.sh \
    --smtp-user "$SMTP_USERNAME" \
    --smtp-pass "$SMTP_PASSWORD" \
    app start
```

### Security Considerations

1. Password Requirements:
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one lowercase letter
   - At least one number
   - At least one special character

2. Rate Limiting:
   - 5 login attempts per 5 minutes
   - Rate limiting on password reset requests
   - IP-based rate limiting for API endpoints

3. Token Security:
   - JWT tokens expire after 24 hours
   - Refresh tokens for seamless user experience
   - Secure token storage in Redis
   - HTTPS-only cookie settings in production

4. Environment Security:
   - Sensitive credentials stored as environment variables
   - Configuration files with restricted permissions (600)
   - Secure headers with CORS and CSP settings
   - SSL/TLS enforcement in production

## Managing Static Assets

### Copying the Entire Static Directory

For a comprehensive approach, copy the entire static directory:

1. Locate your source static directory:
   ```bash
   find ~/nba-analytics -type d -name "static"
   ```

2. Copy the entire directory:
   ```bash
   # Replace SOURCE_STATIC_DIR with the actual path
   SOURCE_STATIC_DIR=~/nba-analytics/static
   
   # Backup any existing static directory
   if [ -d "/var/www/yunoball/static" ]; then
       sudo mv /var/www/yunoball/static /var/www/yunoball/static.bak
   fi
   
   # Copy the entire static directory
   sudo cp -r ${SOURCE_STATIC_DIR} /var/www/yunoball/
   
   # Set proper ownership and permissions
   sudo chown -R ubuntu:ubuntu /var/www/yunoball/static
   sudo find /var/www/yunoball/static -type d -exec chmod 755 {} \;
   sudo find /var/www/yunoball/static -type f -exec chmod 644 {} \;
   ```

3. Verify the copy was successful:
   ```bash
   find /var/www/yunoball/static -type d | sort
   ```

### Using Node.js Build Process

If you need to build CSS and JS assets:

```bash
# Navigate to your project directory
cd /var/www/yunoball

# Install Node.js dependencies
npm install

# Build assets
npm run build
```

## Database Configuration

### PostgreSQL Setup

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create a database and user
sudo -u postgres psql -c "CREATE DATABASE yunoball;"
sudo -u postgres psql -c "CREATE USER yunoball_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE yunoball TO yunoball_user;"
```

### Redis Setup

```bash
# Install Redis
sudo apt install -y redis-server

# Configure Redis to start on boot
sudo systemctl enable redis-server

# Start Redis
sudo systemctl start redis-server
```

## CloudWatch Monitoring Configuration

### Setting Up CloudWatch Access

1. Install required packages:
   ```bash
   pip install boto3 python-dotenv
   ```

2. Configure AWS credentials:
   - For local development, create a `.env` file:
     ```bash
     AWS_ACCESS_KEY_ID=your_access_key
     AWS_SECRET_ACCESS_KEY=your_secret_key
     AWS_REGION=us-east-1
     FORCE_LOCAL=true  # Set to false to enable CloudWatch
     ```
   - For EC2 deployment, attach the `CloudWatchMonitorRole` IAM role

3. Initialize CloudWatch resources:
   ```bash
   # Create dashboard and alarms
   python setup_dashboard.py
   python setup_alarms.py
   ```

### Monitoring Features

- API endpoint performance metrics
- Database query performance tracking
- User session monitoring
- Error rate tracking
- Custom metric support

### Viewing Metrics

1. Local Development:
   - Metrics are logged locally when `FORCE_LOCAL=true`
   - View logs in `nba_data_module.log`

2. Production:
   - Access CloudWatch dashboard in AWS Console
   - View real-time metrics and alarms
   - Monitor application performance

### Troubleshooting Monitoring

Check CloudWatch connectivity:
```bash
# Verify AWS credentials
aws configure list

# Test CloudWatch access
aws cloudwatch list-metrics --namespace NBA

# Check CloudWatch logs
aws logs describe-log-groups
```

## Troubleshooting

### Service Not Starting

Check the service logs:

```bash
sudo journalctl -u yunoball.service -n 100
```

### Permission Issues

Ensure proper ownership and permissions:

```bash
sudo chown -R ubuntu:ubuntu /var/www/yunoball
sudo chmod 755 /var/www/yunoball
sudo chmod 664 /var/www/yunoball/nba_data_module.log
```

### Nginx Not Serving the Application

Check Nginx logs:

```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

### Python Import Errors

If you encounter import errors, check the Python path:

```bash
# Add the application directory to the Python path in wsgi.py
import sys
sys.path.insert(0, "/var/www/yunoball")
```

### Redis Connection Issues

Verify Redis is running:

```bash
sudo systemctl status redis-server
redis-cli ping  # Should return PONG
```

### SSL Certificate Issues

If you encounter SSL-related issues:

1. Check certificate status:
```bash
sudo certbot certificates
```

2. Verify Nginx SSL configuration:
```bash
sudo nginx -t
```

3. Check SSL certificate renewal:
```bash
# Test automatic renewal
sudo certbot renew --dry-run

# Check renewal timer status
sudo systemctl status certbot.timer
```

4. Common SSL issues:
   - Domain DNS not properly configured
   - Ports 80/443 not accessible
   - Invalid email address provided
   - Nginx configuration conflicts

To fix SSL issues:
```bash
# Reconfigure SSL for your domain
CERT_EMAIL=your@email.com sudo certbot --nginx -d yourdomain.com --non-interactive --agree-tos --redirect

# Or remove and reinstall certificates
sudo certbot delete
CERT_EMAIL=your@email.com sudo certbot --nginx -d yourdomain.com --non-interactive --agree-tos --redirect
```

## Maintenance

### Updating the Application

```bash
cd /var/www/yunoball
git pull
sudo systemctl restart yunoball.service
```

### Monitoring

```bash
# Check service status
sudo systemctl status yunoball.service

# Monitor logs in real-time
sudo journalctl -u yunoball.service -f
```

### SSL Certificate Maintenance

```bash
# Check certificate status and expiration
sudo certbot certificates

# Test automatic renewal
sudo certbot renew --dry-run

# Force renewal (if needed)
sudo certbot renew --force-renewal
```

### Backup

```bash
# Example backup command
sudo rsync -av /var/www/yunoball/ /backup/yunoball-$(date +%Y%m%d)/
```

### Regular Maintenance Tasks

1. Update system packages:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

2. Check disk space:
   ```bash
   df -h
   ```

3. Monitor log file sizes:
   ```bash
   sudo find /var/log -type f -name "*.log" -size +100M
   ```

4. Rotate logs if needed:
   ```bash
   sudo logrotate -f /etc/logrotate.conf
   ```

5. Check SSL certificate status:
   ```bash
   sudo certbot certificates
   sudo systemctl status certbot.timer
   ```

## Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)

## Keeping Documentation Updated

To ensure this documentation stays up-to-date with your codebase, we provide a script to sync documentation and scripts to your local repository:

```bash
# If you're on the production server
./scripts/sync_to_local.sh /path/to/your/local/repository
```

This script will copy:
- This DEVELOPER.md file
- The wsgi.py.template file
- All scripts in the scripts directory
- Make all scripts executable in the local repository

Alternatively, you can manually copy files:

```bash
# If you're on the production server
cp /var/www/yunoball/DEVELOPER.md /path/to/your/local/repository/

# If you've made changes locally
cp DEVELOPER.md /var/www/yunoball/
```

Whenever you make significant changes to the deployment process or application structure, update this documentation to reflect those changes.

## Data Ingestion

### Local Setup (Recommended)

Data ingestion is designed to run locally to prevent proxy rate limit issues on AWS. To set up automated data ingestion:

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Set up cron jobs locally
sudo ./scripts/setup_cron.sh
```

The following cron jobs will be created:
- Daily ingestion: Updates recent game data and statistics
- Weekly ingestion: Performs a full data refresh

### AWS Deployment Note

⚠️ **Important**: Data ingestion is intentionally disabled on AWS to prevent proxy overuse. Instead:
1. Run ingestion jobs locally
2. Push the results to the production database
3. The AWS deployment will serve the updated data

This approach helps:
- Prevent proxy rate limit issues
- Reduce AWS resource usage
- Maintain better control over data updates

To modify the ingestion schedule, edit the cron scripts locally at:
- `/etc/cron.daily/yunoball-daily-ingest`
- `/etc/cron.weekly/yunoball-weekly-ingest`