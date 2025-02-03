import subprocess
import os
import signal
import sys
from app import create_app
from cache_warmer import warm_cache  # Import the cache warming function

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
        if "--warm-cache" in sys.argv:
            warm_cache()  # Trigger cache warming
        else:
            app.run(debug=True)
    finally:
        stop_redis(redis_process)