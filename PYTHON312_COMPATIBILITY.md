# Python 3.12 Compatibility

## Issue

When deploying the YunoBall application with Python 3.12, you may encounter the following error:

```
AttributeError: module 'pkgutil' has no attribute 'ImpImporter'. Did you mean: 'zipimporter'?
```

This error occurs because `pkgutil.ImpImporter` was removed in Python 3.12, but older versions of setuptools still try to use it.

## Solution

We've provided scripts to create a clean virtual environment with a compatible version of setuptools (68.0.0 or later) and to run the deployment scripts with this environment.

## Setup Instructions

1. **Set up the clean virtual environment**:

   ```bash
   chmod +x setup_clean_venv.sh
   ./setup_clean_venv.sh
   ```

   This script will:
   - Create a virtual environment at `~/clean_venv`
   - Install a compatible version of setuptools
   - Install all project dependencies

2. **Run the deployment with the clean virtual environment**:

   ```bash
   chmod +x run_with_clean_venv.sh
   ./run_with_clean_venv.sh --branch developProxy deploy
   ```

   This wrapper script will:
   - Set the necessary environment variables
   - Run yunoball.sh with the clean virtual environment

3. **Optionally, modify the existing scripts** (if you want to make the changes permanent):

   ```bash
   cd scripts
   chmod +x use_clean_venv.sh
   sudo ./use_clean_venv.sh
   ```

   This script will:
   - Back up the original scripts
   - Modify them to use the clean virtual environment

## Usage Examples

- **Deploy the application**:
  ```bash
  ./run_with_clean_venv.sh --branch developProxy deploy
  ```

- **Update the application**:
  ```bash
  ./run_with_clean_venv.sh --branch developProxy update
  ```

- **Start the application**:
  ```bash
  ./run_with_clean_venv.sh app start
  ```

- **Start without proxy support**:
  ```bash
  ./run_with_clean_venv.sh --no-proxy app start
  ```

- **Run data ingestion**:
  ```bash
  ./run_with_clean_venv.sh ingest daily
  ```

## Troubleshooting

If you encounter any issues:

1. **Check the clean virtual environment**:
   ```bash
   source ~/clean_venv/bin/activate
   pip list
   ```
   Ensure setuptools version is 68.0.0 or later.

2. **Recreate the clean virtual environment**:
   ```bash
   rm -rf ~/clean_venv
   ./setup_clean_venv.sh
   ```

3. **Check for error messages**:
   ```bash
   ./run_with_clean_venv.sh app logs
   ```

## Restoring Original Scripts

If you've modified the original scripts and want to restore them:

```bash
cd scripts
cp backup/deploy.sh.bak deploy.sh
cp backup/update.sh.bak update.sh
cp backup/manage.sh.bak manage.sh
cp backup/ingest.sh.bak ingest.sh
cp backup/setup_cron.sh.bak setup_cron.sh
``` 