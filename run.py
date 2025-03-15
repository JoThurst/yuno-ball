import subprocess
import os
import signal
import sys

# Set default environment variables
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
    print("🔄 Forcing local (direct) connection for API calls")
    sys.argv.remove("--local")

# Now import app modules after environment variables are set
from app import create_app
from cache_warmer import warm_cache  # Import the cache warming function
from app.middleware.rate_limiter import apply_global_rate_limiting

# Path to Redis executable
REDIS_PATH = os.path.join(os.getcwd(), 'redis', 'redis-server.exe')

# Start Redis server
def start_redis():
    try:
        redis_process = subprocess.Popen([REDIS_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ Redis server started successfully.")
        return redis_process
    except Exception as e:
        print(f"❌ Failed to start Redis: {e}")
        return None

# Stop Redis server
def stop_redis(redis_process):
    if redis_process:
        redis_process.terminate()
        redis_process.wait()
        print("🛑 Redis server stopped.")

# Start Redis
redis_process = start_redis()

# Start Flask app
app = create_app()

# Apply rate limiting only when using proxy or in production
if not os.environ["FORCE_LOCAL"] == "true":
    print("🔒 Applying rate limiting (60 requests per minute per IP)")
    apply_global_rate_limiting(app, requests_per_minute=60)
else:
    print("🔓 Running in local mode - rate limiting disabled")

if __name__ == "__main__":
    try:
        if "--warm-cache" in sys.argv:
            warm_cache()  # Trigger cache warming
            debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
            app.run(debug=debug_mode, host='0.0.0.0', port=8000)
        else:
            debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
            app.run(debug=debug_mode, host='0.0.0.0', port=8000)
    finally:
        stop_redis(redis_process)