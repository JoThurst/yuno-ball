"""
NBA Analytics Web Application Runner
This module serves as the main entry point for the NBA analytics web application.
It handles the initialization and shutdown of the Redis server and Flask application.
The module performs the following main tasks:
1. Starts a Redis server for caching
2. Initializes and runs a Flask web application
3. Provides option for cache warming via command line argument
4. Ensures proper cleanup of Redis server on application shutdown
Dependencies:
    - Flask
    - Redis
    - subprocess (for Redis server management)
    - sys, os (for system operations)
Environment Variables:
    - FLASK_DEBUG: Controls debug mode ("true"/"false")
Usage:
    Standard run:
        python run.py
    With cache warming:
        python run.py --warm-cache
"""

import subprocess
import os
import sys
from flask import Flask
from app import create_app
from cache_warmer import warm_cache  # Import the cache warming function

# Path to Redis executable
REDIS_PATH: str = os.path.join(os.getcwd(), "redis", "redis-server.exe")


# Start Redis server
def start_redis():
    """
    Attempts to start a Redis server process.

    This function launches a Redis server using the path specified in REDIS_PATH.
    It creates a subprocess and captures both stdout and stderr streams.

    Returns:
        subprocess.Popen: The Redis server process if started successfully
        None: If the Redis server fails to start

    Raises:
        Exception: Any exception that occurs during Redis server startup will be caught,
                  logged and None will be returned
    """
    try:
        process = subprocess.Popen(
            args=[REDIS_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        print("✅ Redis server started successfully.")
        return process
    except Exception as e:
        print(f"❌ Failed to start Redis: {e}")
        return None


# Stop Redis server
def stop_redis(process) -> None:
    """
    Stops a running Redis server process.

    Args:
        process: A subprocess.Popen object representing the Redis server process.
            If None, no action is taken.

    Returns:
        None

    Side Effects:
        - Terminates the given Redis process
        - Waits for process completion
        - Prints confirmation message when server is stopped
    """
    if process:
        process.terminate()
        process.wait()
        print("🛑 Redis server stopped.")


# Start Redis
redis_process = start_redis()

# Start Flask app
app: Flask = create_app()

if __name__ == "__main__":
    try:
        debug_mode: bool = (
            os.getenv(key="FLASK_DEBUG", default="false").lower() == "true"
        )
        if "--warm-cache" in sys.argv:
            warm_cache()  # Trigger cache warming
            app.run(debug=debug_mode)
        else:
            app.run(debug=debug_mode)
    finally:
        stop_redis(process=redis_process)
