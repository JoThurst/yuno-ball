import os
import logging
import time
import socket
from threading import Lock
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 4))  # Default to 5 workers if not set

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
FORCE_LOCAL = os.getenv("FORCE_LOCAL", "false")
FORCE_PROXY = os.getenv("FORCE_PROXY", "false")
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false")
#print(f"Config Utils- \nFORCE_LOCAL: {FORCE_LOCAL}, FORCE_PROXY: {FORCE_PROXY}, PROXY_ENABLED: {PROXY_ENABLED}")

logger.debug(f"Raw env values - FORCE_LOCAL: {FORCE_LOCAL}, FORCE_PROXY: {FORCE_PROXY}, PROXY_ENABLED: {PROXY_ENABLED}")

# Convert to boolean after logging raw values
FORCE_LOCAL = FORCE_LOCAL.lower() == "true"
FORCE_PROXY = FORCE_PROXY.lower() == "true"
PROXY_ENABLED = PROXY_ENABLED.lower() == "true"
#print(f"Config Utils after boolean conversion- \nFORCE_LOCAL: {FORCE_LOCAL}, FORCE_PROXY: {FORCE_PROXY}, PROXY_ENABLED: {PROXY_ENABLED}")

# Determine if proxy should be enabled
if FORCE_PROXY or PROXY_ENABLED:
    PROXY_ENABLED = True
    logger.info("Proxy mode enabled - using proxy for API calls")
elif FORCE_LOCAL:
    PROXY_ENABLED = False
    logger.info("Local mode forced - proxies disabled")
elif is_running_on_aws():
    PROXY_ENABLED = True
    logger.info("Running on AWS - enabling proxy mode")
else:
    PROXY_ENABLED = False
    logger.info("Local mode - proxies disabled")

# SmartProxy / Decodo configuration
# Read from environment variables for security (should be in .env file)
SMARTPROXY_USERNAME = os.getenv("SMARTPROXY_USERNAME", "")
SMARTPROXY_PASSWORD = os.getenv("SMARTPROXY_PASSWORD", "")
SMARTPROXY_HOST = os.getenv("SMARTPROXY_HOST", "gate.decodo.com")
# Decodo residential default is 7000; legacy SmartProxy sticky ports were 10001-10010
SMARTPROXY_PORTS_STR = os.getenv("SMARTPROXY_PORTS", "7000")
SMARTPROXY_PORTS = [port.strip() for port in SMARTPROXY_PORTS_STR.split(",") if port.strip()]
# Proxy URL scheme for requests/nba_api: must be http:// (NOT https://) for Decodo/SmartProxy gateways
SMARTPROXY_SCHEME = os.getenv("SMARTPROXY_SCHEME", "http").lower().strip()
if SMARTPROXY_SCHEME not in ("http", "https", "socks5h", "socks5"):
    logger.warning(f"Invalid SMARTPROXY_SCHEME={SMARTPROXY_SCHEME!r}; falling back to http")
    SMARTPROXY_SCHEME = "http"

# Decodo docs often show usernames as "user-<name>". Do NOT auto-prefix:
# some SmartProxy/Decodo sub-users already work without it, and prefixing breaks auth.
_host_l = (SMARTPROXY_HOST or "").lower()
if (
    SMARTPROXY_USERNAME
    and "decodo.com" in _host_l
    and not SMARTPROXY_USERNAME.startswith("user-")
):
    logger.info(
        "SMARTPROXY_USERNAME has no 'user-' prefix. If Decodo auth fails, "
        "set SMARTPROXY_USERNAME=user-<your_user> in .env"
    )

# Validate that credentials are set
if not SMARTPROXY_USERNAME or not SMARTPROXY_PASSWORD:
    logger.warning("SMARTPROXY_USERNAME or SMARTPROXY_PASSWORD not set in environment variables!")
    logger.warning("   Please add them to your .env file. See .env.example for template.")
    logger.warning("   Proxy functionality will not work until credentials are configured.")

# Build proxy list from credentials (only if credentials are set)
PROXY_LIST = []
if SMARTPROXY_USERNAME and SMARTPROXY_PASSWORD and SMARTPROXY_PORTS:
    PROXY_LIST = [
        f"{SMARTPROXY_SCHEME}://{SMARTPROXY_USERNAME}:{SMARTPROXY_PASSWORD}@{SMARTPROXY_HOST}:{port}"
        for port in SMARTPROXY_PORTS
    ]
    logger.info(
        f"Proxy list built: {len(PROXY_LIST)} endpoints "
        f"({SMARTPROXY_SCHEME}://***:***@{SMARTPROXY_HOST}:[{','.join(SMARTPROXY_PORTS)}])"
    )
else:
    logger.warning("Proxy list is empty - credentials not configured in .env file")

DEFAULT_PROXY = PROXY_LIST[0] if PROXY_LIST else None

# Headers aligned with nba_api STATS_HEADERS
# https://github.com/swar/nba_api — stats.nba.com expects x-nba-stats-* tokens.
# Overriding without these often causes hangs/timeouts through proxies.
try:
    from nba_api.stats.library.http import STATS_HEADERS as _NBA_STATS_HEADERS
    DEFAULT_HEADERS = dict(_NBA_STATS_HEADERS)
except Exception:
    DEFAULT_HEADERS = {
        "Host": "stats.nba.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) "
            "Gecko/20100101 Firefox/72.0"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
        "Connection": "keep-alive",
        "Referer": "https://stats.nba.com/",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }

def get_proxy():
    """
    Returns a proxy to use for API requests.
    """
    # Re-check environment variables at runtime
    force_proxy = os.getenv("FORCE_PROXY", "false")
    proxy_enabled = os.getenv("PROXY_ENABLED", "false")
    force_local = os.getenv("FORCE_LOCAL", "false")
    
    logger.debug(f"Runtime check raw values - FORCE_LOCAL: {force_local}, FORCE_PROXY: {force_proxy}, PROXY_ENABLED: {proxy_enabled}")
    
    # Convert to boolean after logging raw values
    force_proxy = force_proxy.lower() == "true"
    proxy_enabled = proxy_enabled.lower() == "true"
    force_local = force_local.lower() == "true"
    
    # Determine if proxy should be used
    use_proxy = force_proxy or proxy_enabled
    if force_local:
        use_proxy = False
        logger.debug("Runtime check: Local mode forced - proxies disabled")
    elif use_proxy:
        logger.debug("Runtime check: Proxy mode enabled")
    elif is_running_on_aws():
        use_proxy = True
        logger.debug("Runtime check: Running on AWS - proxy enabled")
    
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
    
    def __init__(self, max_requests=25, interval=90):
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


