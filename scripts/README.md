# YunoBall Deployment Scripts

This directory contains scripts for deploying and managing the YunoBall application on Ubuntu.

## Prerequisites

- Ubuntu 20.04 or newer
- Root or sudo access
- A domain name pointing to your server (e.g., yunoball.xyz)

## Scripts Overview

### 1. `deploy.sh`

This script automates the initial deployment of the YunoBall application. It:

- Installs all necessary dependencies
- Clones the repository
- Sets up a Python virtual environment
- Configures Nginx with SSL
- Creates a systemd service
- Sets up firewall rules
- Configures fail2ban for security

**Usage:**
```bash
sudo ./deploy.sh
```

### 2. `update.sh`

This script updates the YunoBall application with the latest changes from the repository.

**Usage:**
```bash
sudo ./update.sh
```

### 3. `manage.sh`

This script provides commands to manage the YunoBall application.

**Usage:**
```bash
sudo ./manage.sh [command]
```

**Commands:**
- `start` - Start the YunoBall application
- `stop` - Stop the YunoBall application
- `restart` - Restart the YunoBall application
- `status` - Check the status of the YunoBall application
- `logs` - View the application logs
- `nginx-logs` - View the Nginx access and error logs
- `help` - Display help message

### 4. `ingest.sh`

This script runs data ingestion tasks for the YunoBall application.

**Usage:**
```bash
sudo ./ingest.sh [command]
```

**Commands:**
- `daily` - Run daily data ingestion tasks
- `full` - Run full data ingestion (one-time/weekly tasks)
- `help` - Display help message

### 5. `setup_cron.sh`

This script sets up cron jobs for automated data ingestion.

**Usage:**
```bash
sudo ./setup_cron.sh
```

## Deployment Process

1. **Initial Deployment:**
   ```bash
   sudo ./deploy.sh
   ```

2. **Set Up Automated Data Ingestion:**
   ```bash
   sudo ./setup_cron.sh
   ```

3. **Managing the Application:**
   ```bash
   # Start the application
   sudo ./manage.sh start
   
   # Check the status
   sudo ./manage.sh status
   
   # View logs
   sudo ./manage.sh logs
   ```

4. **Updating the Application:**
   ```bash
   sudo ./update.sh
   ```

5. **Running Data Ingestion Manually:**
   ```bash
   # Run daily ingestion
   sudo ./ingest.sh daily
   
   # Run full ingestion
   sudo ./ingest.sh full
   ```

## Configuration

Before running the scripts, you should modify the configuration variables at the top of each script to match your environment:

- `APP_NAME` - The name of your application (default: "yunoball")
- `DOMAIN` - Your domain name (default: "yunoball.xyz")
- `APP_DIR` - The directory where the application will be installed (default: "/var/www/yunoball")
- `REPO_URL` - The URL of your Git repository
- `EMAIL` - Your email address for Let's Encrypt SSL certificates

## Troubleshooting

If you encounter issues:

1. Check the application logs:
   ```bash
   sudo ./manage.sh logs
   ```

2. Check the Nginx logs:
   ```bash
   sudo ./manage.sh nginx-logs
   ```

3. Verify the Nginx configuration:
   ```bash
   sudo nginx -t
   ```

4. Check the systemd service status:
   ```bash
   sudo systemctl status yunoball.service
   ``` 