import os
import sys
import logging
import schedule
import time
from datetime import datetime
import subprocess
from pathlib import Path
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cleanup_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_cleanup():
    """Run the database cleanup script"""
    try:
        script_dir = Path(__file__).parent
        cleanup_script = script_dir / 'database_cleanup.py'
        optimize_script = script_dir / 'optimize_database.sql'
        
        # Run the Python cleanup script
        logger.info("Starting database cleanup...")
        result = subprocess.run([sys.executable, str(cleanup_script)], 
                              capture_output=True, 
                              text=True)
        
        if result.returncode != 0:
            logger.error(f"Cleanup script failed: {result.stderr}")
            return False
        
        logger.info("Database cleanup completed successfully")
        
        # Run the SQL optimization script
        logger.info("Starting database optimization...")
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.error("DATABASE_URL environment variable not set")
            return False
            
        optimize_cmd = f"psql {db_url} -f {optimize_script}"
        result = subprocess.run(optimize_cmd, 
                              shell=True, 
                              capture_output=True, 
                              text=True)
        
        if result.returncode != 0:
            logger.error(f"Optimization script failed: {result.stderr}")
            return False
            
        logger.info("Database optimization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error running cleanup tasks: {e}")
        return False

def schedule_cleanup():
    """Schedule cleanup tasks"""
    # Schedule daily cleanup at 2 AM
    schedule.every().day.at("02:00").do(run_cleanup)
    
    # Schedule weekly optimization on Sunday at 3 AM
    schedule.every().sunday.at("03:00").do(run_cleanup)
    
    logger.info("Cleanup scheduler started")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Cleanup scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            time.sleep(300)  # Wait 5 minutes before retrying on error

def main():
    parser = argparse.ArgumentParser(description='Database cleanup scheduler')
    parser.add_argument('--run-now', action='store_true', 
                       help='Run cleanup immediately instead of scheduling')
    args = parser.parse_args()
    
    if args.run_now:
        logger.info("Running cleanup immediately...")
        success = run_cleanup()
        sys.exit(0 if success else 1)
    else:
        schedule_cleanup()

if __name__ == "__main__":
    main() 