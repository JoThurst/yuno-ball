import subprocess
import os
import signal
import sys
from app import create_app
from cache_warmer import warm_cache  # Import the cache warming function

# Set environment variables for proxy configuration
# Uncomment and modify these lines to enable proxy on AWS
# os.environ["PROXY_ENABLED"] = "true"
# os.environ["FORCE_LOCAL"] = "false"
# os.environ["FORCE_PROXY"] = "false"

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

if __name__ == "__main__":
    try:
        # Check for proxy configuration in command line arguments
        if "--proxy" in sys.argv:
            os.environ["FORCE_PROXY"] = "true"
            print("🔄 Forcing proxy usage for API calls")
            sys.argv.remove("--proxy")
        
        if "--local" in sys.argv:
            os.environ["FORCE_LOCAL"] = "true"
            print("🔄 Forcing local (direct) connection for API calls")
            sys.argv.remove("--local")
            
        if "--warm-cache" in sys.argv:
            warm_cache()  # Trigger cache warming
            debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
            app.run(debug=debug_mode)
        else:
            debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
            app.run(debug=debug_mode, host='0.0.0.0', port=8000)
    finally:
        stop_redis(redis_process)