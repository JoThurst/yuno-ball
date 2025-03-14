import os
import subprocess
import platform
import logging
from datetime import datetime
from pathlib import Path
import psycopg2
from app.config import get_connection, release_connection

class DatabaseManager:
    """Manages database operations including backups and maintenance for both local and cloud environments."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_windows = platform.system().lower() == "windows"
        self.backup_base_dir = self._get_backup_dir()
        
    def _get_backup_dir(self):
        """Get the appropriate backup directory based on the operating system."""
        if self.is_windows:
            base = os.path.join(os.getenv('LOCALAPPDATA'), 'YunoBall', 'backups')
        else:
            base = '/var/backup/yunoball'
        return base

    def _ensure_backup_dirs(self):
        """Create backup directories if they don't exist."""
        dirs = ['daily', 'weekly', 'monthly', 'pre_migration']
        for dir_name in dirs:
            dir_path = os.path.join(self.backup_base_dir, dir_name)
            os.makedirs(dir_path, exist_ok=True)

    def _get_db_url_components(self):
        """Extract components from DATABASE_URL environment variable."""
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable not set")
        
        try:
            conn = psycopg2.connect(db_url)
            params = conn.get_dsn_parameters()
            conn.close()
            return params
        except Exception as e:
            self.logger.error(f"Error parsing DATABASE_URL: {e}")
            raise

    def create_backup(self, backup_type='daily'):
        """Create a database backup."""
        self._ensure_backup_dirs()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        backup_file = os.path.join(self.backup_base_dir, backup_type, f'yunoball_{backup_type}_{timestamp}.sql')
        
        try:
            db_params = self._get_db_url_components()
            
            if self.is_windows:
                # Windows pg_dump command
                cmd = [
                    'pg_dump',
                    '--dbname=postgresql://{user}:{password}@{host}:{port}/{dbname}'.format(**db_params),
                    '--format=custom',
                    f'--file={backup_file}'
                ]
            else:
                # Linux pg_dump command
                cmd = [
                    'pg_dump',
                    '-h', db_params['host'],
                    '-p', db_params['port'],
                    '-U', db_params['user'],
                    '-d', db_params['dbname'],
                    '-F', 'c',
                    '-f', backup_file
                ]
                
                # Set PGPASSWORD environment variable for Linux
                os.environ['PGPASSWORD'] = db_params['password']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"Successfully created {backup_type} backup: {backup_file}")
                return backup_file
            else:
                self.logger.error(f"Backup failed: {result.stderr}")
                raise Exception(f"Backup failed: {result.stderr}")
                
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            raise
        finally:
            # Clean up PGPASSWORD
            if not self.is_windows and 'PGPASSWORD' in os.environ:
                del os.environ['PGPASSWORD']

    def restore_backup(self, backup_file):
        """Restore a database from backup file."""
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
        try:
            db_params = self._get_db_url_components()
            
            if self.is_windows:
                cmd = [
                    'pg_restore',
                    '--dbname=postgresql://{user}:{password}@{host}:{port}/{dbname}'.format(**db_params),
                    '--clean',
                    backup_file
                ]
            else:
                cmd = [
                    'pg_restore',
                    '-h', db_params['host'],
                    '-p', db_params['port'],
                    '-U', db_params['user'],
                    '-d', db_params['dbname'],
                    '--clean',
                    backup_file
                ]
                os.environ['PGPASSWORD'] = db_params['password']
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.logger.info(f"Successfully restored backup: {backup_file}")
            else:
                self.logger.error(f"Restore failed: {result.stderr}")
                raise Exception(f"Restore failed: {result.stderr}")
                
        except Exception as e:
            self.logger.error(f"Error restoring backup: {e}")
            raise
        finally:
            if not self.is_windows and 'PGPASSWORD' in os.environ:
                del os.environ['PGPASSWORD']

    def cleanup_old_backups(self, backup_type, keep_count):
        """Remove old backups keeping only the specified number of recent ones."""
        backup_dir = os.path.join(self.backup_base_dir, backup_type)
        if not os.path.exists(backup_dir):
            return
            
        backups = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith('.sql')],
            reverse=True
        )
        
        for old_backup in backups[keep_count:]:
            try:
                os.remove(os.path.join(backup_dir, old_backup))
                self.logger.info(f"Removed old backup: {old_backup}")
            except Exception as e:
                self.logger.error(f"Failed to remove old backup {old_backup}: {e}")

    def verify_backup(self, backup_file):
        """Verify the integrity of a backup file."""
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
        try:
            cmd = ['pg_restore', '--list', backup_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error verifying backup {backup_file}: {e}")
            return False
