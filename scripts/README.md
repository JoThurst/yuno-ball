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
- Clones the repository (with branch selection)
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
- `start` - Start the YunoBall application with proxy support
- `start-no-proxy` - Start the YunoBall application without proxy support
- `stop` - Stop the YunoBall application
- `restart` - Restart the YunoBall application with proxy support
- `restart-no-proxy` - Restart the YunoBall application without proxy support
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

## Master Script: `yunoball.sh`

The master script provides a unified interface for all YunoBall management scripts.

**Usage:**
```bash
sudo ./yunoball.sh [options] [command] [subcommand]
```

**Options:**
- `--branch NAME` - Specify a Git branch to use (default: developProxy)
- `--no-proxy` - Run without proxy support (for local development)

**Examples:**
```bash
# Deploy using default branch (developProxy)
sudo ./yunoball.sh deploy

# Deploy using a specific branch
sudo ./yunoball.sh --branch main deploy

# Update using a specific branch
sudo ./yunoball.sh --branch feature-branch update

# Start the application with proxy support
sudo ./yunoball.sh app start

# Start the application without proxy support
sudo ./yunoball.sh --no-proxy app start

# Run daily ingestion
sudo ./yunoball.sh ingest daily
```

## Deployment Process

1. **Initial Deployment:**
   ```bash
   # Deploy using default branch (developProxy)
   sudo ./yunoball.sh deploy
   
   # Or deploy using a specific branch
   sudo ./yunoball.sh --branch main deploy
   ```

2. **Set Up Automated Data Ingestion:**
   ```bash
   sudo ./yunoball.sh cron
   ```

3. **Managing the Application:**
   ```bash
   # Start the application with proxy support
   sudo ./yunoball.sh app start
   
   # Start the application without proxy support (for local testing)
   sudo ./yunoball.sh --no-proxy app start
   
   # Check the status
   sudo ./yunoball.sh app status
   
   # View logs
   sudo ./yunoball.sh app logs
   ```

4. **Updating the Application:**
   ```bash
   # Update using default branch
   sudo ./yunoball.sh update
   
   # Update using a specific branch
   sudo ./yunoball.sh --branch feature-branch update
   ```

5. **Running Data Ingestion Manually:**
   ```bash
   # Run daily ingestion
   sudo ./yunoball.sh ingest daily
   
   # Run full ingestion
   sudo ./yunoball.sh ingest full
   ```

## Configuration

Before running the scripts, you should modify the configuration variables at the top of each script to match your environment:

- `APP_NAME` - The name of your application (default: "yunoball")
- `DOMAIN` - Your domain name (default: "yunoball.xyz")
- `APP_DIR` - The directory where the application will be installed (default: "/var/www/yunoball")
- `REPO_URL` - The URL of your Git repository
- `DEFAULT_BRANCH` - The default Git branch to use (default: "developProxy")
- `EMAIL` - Your email address for Let's Encrypt SSL certificates

## Proxy Configuration

The scripts are designed to automatically enable proxy support for NBA API calls when running on AWS. This is crucial for accessing the NBA API, which may block requests from AWS IP addresses.

- **For production (AWS)**: Proxy support is enabled by default
- **For local development**: You can disable proxy support using the `--no-proxy` option

## Troubleshooting

If you encounter issues:

1. Check the application logs:
   ```bash
   sudo ./yunoball.sh app logs
   ```

2. Check the Nginx logs:
   ```bash
   sudo ./yunoball.sh app nginx-logs
   ```

3. Verify the Nginx configuration:
   ```bash
   sudo nginx -t
   ```

4. Check the systemd service status:
   ```bash
   sudo systemctl status yunoball.service
   ``` 