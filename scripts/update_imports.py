#!/usr/bin/env python3
"""
Script to update imports from db_config to app.config in all Python files.
"""

import os
import re
from pathlib import Path

def update_file(file_path):
    """Update imports in a single file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace imports
    content = content.replace(
        'from db_config import get_connection, release_connection',
        'from app.config import get_connection, release_connection'
    )
    content = content.replace(
        'from db_config import get_connection',
        'from app.config import get_connection'
    )
    content = content.replace(
        'from db_config import API_KEY',
        'from app.config import API_KEY'
    )
    content = content.replace(
        'import db_config',
        'import app.config as db_config'  # For backward compatibility if needed
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    """Update imports in all Python files."""
    # Get the project root directory
    root_dir = Path(__file__).parent.parent
    
    # Directories to process
    dirs_to_process = [
        root_dir / 'app' / 'models',
        root_dir / 'app' / 'routes',
        root_dir / 'app' / 'services',
        root_dir / 'app' / 'utils'
    ]
    
    # Process each directory
    for directory in dirs_to_process:
        if directory.exists():
            print(f"Processing directory: {directory}")
            for file_path in directory.glob('**/*.py'):
                print(f"Updating file: {file_path}")
                update_file(file_path)
    
    # Also process files in the app directory
    app_dir = root_dir / 'app'
    for file_path in app_dir.glob('*.py'):
        print(f"Updating file: {file_path}")
        update_file(file_path)

if __name__ == '__main__':
    main()
    print("Import updates completed successfully!") 