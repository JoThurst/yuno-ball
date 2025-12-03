"""
Daily Ingest Script - Orchestrates both fetch and calculate tasks.

This is the main entry point that runs the full daily pipeline:
1. Fetch data from NBA APIs (daily_fetch.py)
2. Run calculations on fetched data (daily_calculate.py)

For granular control, run the individual scripts directly:
  python daily_fetch.py --help
  python daily_calculate.py --help

Usage:
    python daily_ingest.py                    # Run full pipeline (all tasks)
    python daily_ingest.py --fetch-only       # Only fetch, skip calculations
    python daily_ingest.py --calc-only        # Only calculate, skip fetching
    python daily_ingest.py --fetch-tasks players rosters
    python daily_ingest.py --calc-tasks streaks heat
    python daily_ingest.py --list             # List all available tasks

See docs/DAILY_SCRIPTS.md for full documentation.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to Python path FIRST
project_root = Path(__file__).parent.absolute()
project_root_str = str(project_root)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

import logging
import traceback
import subprocess
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# Set up logging
logging.basicConfig(
    filename="daily_ingest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)


# Task definitions (for --list display)
FETCH_TASKS = ['players', 'rosters', 'gamelogs', 'schedule', 'future', 
               'teamstats', 'leagueteam', 'leagueplayer', 'injury', 'odds']

CALC_TASKS = ['streaks', 'heat', 'consistency', 'schedule', 
              'metrics', 'flags', 'environment']


def get_current_season():
    """Get current NBA season string."""
    now = datetime.now()
    if 10 <= now.month <= 12:
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    return f"{now.year - 1}-{str(now.year)[-2:]}"


def run_script(script_name: str, args: list = None) -> bool:
    """Run a Python script with arguments."""
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)
    
    logging.info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        logging.error(f"Script failed: {script_name} with code {e.returncode}")
        return False
    except Exception as e:
        logging.error(f"Error running {script_name}: {e}")
        return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Daily NBA data ingestion pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python daily_ingest.py                              # Run everything
  python daily_ingest.py --fetch-only                 # Only API fetching
  python daily_ingest.py --calc-only                  # Only calculations
  python daily_ingest.py --fetch-tasks players rosters --calc-tasks streaks
  python daily_ingest.py --list                       # Show all tasks
  python daily_ingest.py --proxy                      # Use proxy for API calls
  python daily_ingest.py --local                      # Force local/direct API calls

For more granular control, run scripts directly:
  python daily_fetch.py --help
  python daily_calculate.py --help
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--fetch-only', action='store_true',
                           help='Only run fetch tasks, skip calculations')
    mode_group.add_argument('--calc-only', action='store_true',
                           help='Only run calculations, skip fetching')
    
    # Task selection
    parser.add_argument('--fetch-tasks', nargs='+', choices=FETCH_TASKS,
                       help='Specific fetch tasks to run')
    parser.add_argument('--calc-tasks', nargs='+', choices=CALC_TASKS,
                       help='Specific calculation tasks to run')
    parser.add_argument('--exclude-fetch', nargs='+', choices=FETCH_TASKS,
                       help='Fetch tasks to exclude')
    parser.add_argument('--exclude-calc', nargs='+', choices=CALC_TASKS,
                       help='Calculation tasks to exclude')
    
    # Other options
    parser.add_argument('--list', action='store_true',
                       help='List all available tasks and exit')
    parser.add_argument('--season', type=str, default=None,
                       help='Override season (e.g., "2024-25")')
    parser.add_argument('--proxy', action='store_true',
                       help='Force proxy usage for API calls')
    parser.add_argument('--local', action='store_true',
                       help='Force local (direct) connection for API calls')
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # List tasks and exit
    if args.list:
        print("\n" + "=" * 60)
        print("DAILY INGEST - Available Tasks")
        print("=" * 60)
        
        print("\nFetch Tasks (daily_fetch.py):")
        print("-" * 40)
        for task in FETCH_TASKS:
            print(f"  {task}")
        
        print("\nCalculation Tasks (daily_calculate.py):")
        print("-" * 40)
        for task in CALC_TASKS:
            print(f"  {task}")
        
        print("\nFor detailed task descriptions, run:")
        print("  python daily_fetch.py --list")
        print("  python daily_calculate.py --list")
        return
    
    current_season = args.season or get_current_season()
    
    logging.info("=" * 70)
    logging.info("DAILY INGEST PIPELINE")
    logging.info(f"Season: {current_season}")
    logging.info("=" * 70)
    
    fetch_success = True
    calc_success = True
    
    # Build script arguments
    common_args = []
    if args.season:
        common_args.extend(['--season', args.season])
    
    # Run fetch tasks
    if not args.calc_only:
        fetch_args = common_args.copy()
        
        if args.proxy:
            fetch_args.append('--proxy')
        if args.local:
            fetch_args.append('--local')
        if args.fetch_tasks:
            fetch_args.extend(['--tasks'] + args.fetch_tasks)
        if args.exclude_fetch:
            fetch_args.extend(['--exclude'] + args.exclude_fetch)
        
        logging.info("-" * 70)
        logging.info("PHASE 1: DATA FETCHING")
        logging.info("-" * 70)
        fetch_success = run_script('daily_fetch.py', fetch_args if fetch_args else None)
        
        if not fetch_success:
            logging.error("Fetch phase failed!")
            if not args.fetch_only:
                logging.info("Continuing to calculations anyway...")
    
    # Run calculation tasks
    if not args.fetch_only:
        calc_args = common_args.copy()
        
        if args.calc_tasks:
            calc_args.extend(['--tasks'] + args.calc_tasks)
        if args.exclude_calc:
            calc_args.extend(['--exclude'] + args.exclude_calc)
        
        logging.info("-" * 70)
        logging.info("PHASE 2: CALCULATIONS")
        logging.info("-" * 70)
        calc_success = run_script('daily_calculate.py', calc_args if calc_args else None)
    
    # Summary
    logging.info("=" * 70)
    logging.info("DAILY INGEST SUMMARY")
    logging.info(f"  Fetch: {'SUCCESS' if fetch_success else 'FAILED'}")
    logging.info(f"  Calculate: {'SUCCESS' if calc_success else 'FAILED'}")
    logging.info("=" * 70)
    
    return 0 if (fetch_success and calc_success) else 1


if __name__ == "__main__":
    sys.exit(main())
