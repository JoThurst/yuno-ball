import os
import logging
import time
import socket
from threading import Lock
import random

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

# Environment detection
def is_running_on_aws():
    """
    Detect if the application is running on AWS.
    Returns True if running on AWS, False otherwise.
    """
    # Check for AWS environment variables
    if os.getenv("AWS_EXECUTION_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return True
    
    # Try to check if the hostname contains 'aws' or 'ec2'
    try:
        hostname = socket.gethostname().lower()
        return 'aws' in hostname or 'ec2' in hostname
    except:
        pass
    
    # Default to environment variable if set, otherwise False
    return False

# Proxy Configuration
# Read from environment variables or use defaults
FORCE_LOCAL = os.getenv("FORCE_LOCAL", "false").lower() == "true"
FORCE_PROXY = os.getenv("FORCE_PROXY", "false").lower() == "true"

# Determine if proxy should be enabled - this is the key part that needs to be fixed
if FORCE_LOCAL:
    PROXY_ENABLED = False
    logger.info("Forcing local mode - proxies disabled")
elif FORCE_PROXY:
    PROXY_ENABLED = True
    logger.info("Forcing proxy mode - proxies enabled")
else:
    PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() == "true" or is_running_on_aws()
    if PROXY_ENABLED:
        logger.info("Proxy enabled - using proxy for API calls")
    else:
        logger.info("Proxy disabled - using direct connection")

# SmartProxy configuration
SMARTPROXY_USERNAME = "user-sppc24ewsr-sessionduration-5"
SMARTPROXY_PASSWORD = "jnD6WnupJ4Zv21i_ai"
SMARTPROXY_HOST = "gate.smartproxy.com"
SMARTPROXY_PORTS = ["10001", "10002", "10003", "10004", "10005", "10006", "10007", "10008", "10009", "10010"]  # Fixed port list

# Build proxy list from SmartProxy credentials
PROXY_LIST = [
    f"https://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@{SMARTPROXY_HOST}:{port}"
    for port in SMARTPROXY_PORTS
]

DEFAULT_PROXY = PROXY_LIST[0] if PROXY_LIST else None

# Custom headers to avoid detection
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.nba.com/',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'DNT': '1'
}

def get_proxy():
    """
    Returns a proxy to use for API requests.
    
    If PROXY_ENABLED is True, returns either a random proxy from PROXY_LIST
    or the DEFAULT_PROXY. If PROXY_ENABLED is False, returns None.
    """
    # Re-check FORCE_PROXY and FORCE_LOCAL environment variables at runtime
    force_proxy = os.getenv("FORCE_PROXY", "false").lower() == "true"
    force_local = os.getenv("FORCE_LOCAL", "false").lower() == "true"
    
    # Determine if proxy should be used based on current environment variables
    use_proxy = False
    if force_local:
        use_proxy = False
        logger.debug("Runtime check: Forcing local mode - proxies disabled")
    elif force_proxy:
        use_proxy = True
        logger.debug("Runtime check: Forcing proxy mode - proxies enabled")
    else:
        use_proxy = PROXY_ENABLED
    
    if not use_proxy:
        logger.debug("Proxies disabled - using direct connection")
        return None
    
    if PROXY_LIST and PROXY_LIST[0]:  # Check if list is not empty
        selected_proxy = random.choice(PROXY_LIST)
        logger.debug(f"Using proxy: {selected_proxy.split('@')[1]}")  # Log only the host:port part for security
        return selected_proxy
    
    return DEFAULT_PROXY

def get_headers():
    """Returns custom headers to use for API requests."""
    return DEFAULT_HEADERS


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


