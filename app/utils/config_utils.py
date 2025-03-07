import os
import logging
import time
from threading import Lock

# Global Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "nba_data_module.log")

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
)

logger = logging.getLogger(__name__)

# Global Rate-Limiting for API Calls
API_RATE_LIMIT = 0.6  # Seconds to sleep between API calls

# Global Configuration for Multi-threading
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 5))  # Default to 5 workers if not set


class RateLimiter:
    """Custom rate limiter to prevent hitting NBA API limits."""
    
    def __init__(self, max_requests=30, interval=60):
        """
        Args:
            max_requests (int): Max API calls per `interval` seconds.
            interval (int): Time window in seconds.
        """
        self.max_requests = max_requests
        self.interval = interval
        self.request_times = []
        self.lock = Lock()

    def wait_if_needed(self):
        """Checks request frequency and sleeps if API limits are reached."""
        with self.lock:
            now = time.time()

            # Remove timestamps older than `interval` seconds
            self.request_times = [t for t in self.request_times if now - t < self.interval]

            if len(self.request_times) >= self.max_requests:
                sleep_time = self.interval - (now - self.request_times[0])
                if sleep_time > 0:
                    print(f"⏳ Rate limit hit. Sleeping for {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)

            # Record the new request
            self.request_times.append(time.time())


