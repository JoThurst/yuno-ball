"""NBA API helpers using nba_api's documented proxy/header interface.

See: https://github.com/swar/nba_api
  - proxy= on endpoints (string URL or host:port)
  - headers= should include nba_api STATS_HEADERS (x-nba-stats-token, etc.)
"""

from app.utils.config_utils import get_headers, logger, PROXY_ENABLED
from app.utils.fetch.proxy_manager import ProxyManager
import json
import os
import dotenv
from requests.exceptions import RequestException

dotenv.load_dotenv()

# Lazy initialization of proxy manager
proxy_manager = None

def get_proxy_manager():
    global proxy_manager
    if proxy_manager is None:
        proxy_manager = ProxyManager()
    return proxy_manager

def get_api_config():
    """
    Returns a dictionary with proxy and headers configuration for NBA API calls.
    
    Returns:
        dict: Configuration with proxy and headers
    """
    # Use nba_api-compatible STATS_HEADERS (not a stripped custom set)
    headers = get_headers()
    
    # Get proxy configuration
    force_proxy = os.getenv("FORCE_PROXY", "false").lower() == "true"
    force_local = os.getenv("FORCE_LOCAL", "false").lower() == "true"
    proxy = None
    # Only use proxy if explicitly requested or if PROXY_ENABLED in non-local mode
    if force_proxy or (PROXY_ENABLED and not force_local):
        proxy = get_proxy_manager().get_healthy_proxy()
        if proxy:
            # Log host:port only
            display = proxy.split("@")[-1] if "@" in proxy else proxy
            logger.debug(f"Using proxy {display} for NBA API request")

    
    return {
        'proxy': proxy,
        'headers': headers,
        'timeout': 120,  # Increased timeout for all connections to handle slow responses
        'retries': 3,     # Consistent retries for all connections
        'backoff_factor': 1.5  # Exponential backoff for retries
    }

def create_api_endpoint(endpoint_class, proxy=None, headers=None, timeout=None, **kwargs):
    """
    Creates an NBA API endpoint with proxy and headers configuration.
    
    Matches nba_api usage (https://github.com/swar/nba_api):
        CommonPlayerInfo(player_id=..., proxy='http://...', headers=STATS_HEADERS, timeout=...)
    
    Args:
        endpoint_class: The NBA API endpoint class to instantiate
        proxy: Optional proxy URL override (avoids picking a second proxy mid-call)
        headers: Optional headers override
        timeout: Optional timeout override
        **kwargs: Additional arguments to pass to the endpoint
        
    Returns:
        An instance of the endpoint with proxy and headers configured
    """
    configured_attempts = int(os.getenv("NBA_API_PROXY_ATTEMPTS", "3"))
    max_attempts = max(1, min(configured_attempts, 3))
    last_exception = None

    for attempt in range(max_attempts):
        api_config = get_api_config()
        selected_proxy = proxy if proxy is not None else api_config["proxy"]
        selected_headers = headers if headers is not None else api_config["headers"]
        selected_timeout = timeout if timeout is not None else api_config["timeout"]
        endpoint_kwargs = dict(kwargs)
        if selected_proxy:
            endpoint_kwargs["proxy"] = selected_proxy
        endpoint_kwargs["headers"] = selected_headers
        endpoint_kwargs["timeout"] = selected_timeout

        try:
            endpoint = endpoint_class(**endpoint_kwargs)
            if selected_proxy:
                get_proxy_manager().mark_success(selected_proxy)
            return endpoint
        except (RequestException, json.JSONDecodeError) as exc:
            last_exception = exc
            if selected_proxy:
                get_proxy_manager().mark_failed(selected_proxy)
            if proxy is not None or attempt >= max_attempts - 1:
                raise
            logger.warning(
                "NBA API transport failure; rotating proxy (%s/%s): %s",
                attempt + 1,
                max_attempts,
                exc,
            )
        except Exception:
            if selected_proxy:
                get_proxy_manager().mark_failed(selected_proxy)
            raise

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("NBA API endpoint creation failed without an exception")
