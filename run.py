import os
import sys
import platform
import socket

# Set default environment variables before any imports
os.environ.setdefault("FORCE_LOCAL", "true")  # Default to local mode
os.environ.setdefault("AWS_REGION", "us-east-1")

# Check command line arguments for deployment mode
if "--proxy" in sys.argv:
    os.environ["FORCE_PROXY"] = "true"
    os.environ["FORCE_LOCAL"] = "false"
    print("🔄 Forcing proxy usage for API calls")
    sys.argv.remove("--proxy")

if "--local" in sys.argv:
    os.environ["FORCE_LOCAL"] = "true"
    os.environ["FORCE_PROXY"] = "false"
    os.environ["PROXY_ENABLED"] = "false"
    print("🔄 Forcing local (direct) connection for API calls")
    sys.argv.remove("--local")

# Redis configuration based on environment
is_windows = platform.system().lower() == 'windows'
redis_process = None

if is_windows:
    import subprocess
    import signal

    # Path to Redis executable for Windows development
    REDIS_PATH = os.path.join(os.getcwd(), 'redis', 'redis-server.exe')

    def start_redis():
        try:
            process = subprocess.Popen([REDIS_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("✅ Redis server started successfully.")
            return process
        except Exception as e:
            print(f"❌ Failed to start Redis: {e}")
            return None

    def stop_redis(process):
        if process:
            process.terminate()
            process.wait()
            print("🛑 Redis server stopped.")
else:
    # On Ubuntu/Linux, Redis is managed by systemd
    print("ℹ️ Using system Redis service")

def create_and_run_app():
    """Create and run the Flask application with proper cleanup."""
    global redis_process
    
    try:
        # Start Redis if needed
        if is_windows:
            if redis_process:
                stop_redis(redis_process)
            redis_process = start_redis()

        # Import app modules after environment variables are set
        from app import create_app
        from cache_warmer import warm_cache
        from app.middleware.rate_limiter import apply_global_rate_limiting

        # Create Flask app (only once!)
        app = create_app()

        # Apply rate limiting only when using proxy or in production
        if not os.environ["FORCE_LOCAL"] == "true":
            print("🔒 Applying rate limiting (60 requests per minute per IP)")
            apply_global_rate_limiting(app, requests_per_minute=60)
        else:
            print("🔓 Running in local mode - rate limiting disabled")

        # Configure the server
        host = '0.0.0.0'  # Listen on all available interfaces
        port = 8000

        # Print startup message with explicit HTTP URLs
        print(" * Running on all addresses (0.0.0.0)")
        print(f" * Local access: http://127.0.0.1:{port}")
        print(f" * Network access: http://{socket.gethostbyname(socket.gethostname())}:{port}")
        print(" * (Press CTRL+C to quit)")

        # Run the application with debug mode in local
        debug_mode = os.environ["FORCE_LOCAL"] == "true"
        app.run(host=host, port=port, debug=debug_mode, use_reloader=debug_mode)

    except Exception as e:
        print(f"Error starting application: {e}")
        raise
    finally:
        # Ensure Redis is stopped on exit
        if is_windows and redis_process:
            stop_redis(redis_process)

if __name__ == '__main__':
    create_and_run_app()