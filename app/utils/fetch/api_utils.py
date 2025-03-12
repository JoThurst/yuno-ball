from app.utils.config_utils import get_headers, logger, PROXY_ENABLED
from app.utils.fetch.proxy_manager import ProxyManager
import os

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
    # Get headers
    headers = get_headers()
    
    # Get proxy configuration
    force_proxy = os.getenv("FORCE_PROXY", "false").lower() == "true"
    force_local = os.getenv("FORCE_LOCAL", "false").lower() == "true"
    
    proxy = None
    # Only use proxy if explicitly requested or if PROXY_ENABLED in non-local mode
    if force_proxy or (PROXY_ENABLED and not force_local):
        proxy = get_proxy_manager().get_healthy_proxy()
        logger.info(f"Using proxy for NBA API request (FORCE_PROXY={force_proxy})")
    else:
        logger.info("Using direct connection for NBA API request (local mode)")
    
    return {
        'proxy': proxy,
        'headers': headers,
        'timeout': 30 if not proxy else 60  # Increased timeout only for proxy connections
    }

def create_api_endpoint(endpoint_class, **kwargs):
    """
    Creates an NBA API endpoint with proxy and headers configuration.
    
    Args:
        endpoint_class: The NBA API endpoint class to instantiate
        **kwargs: Additional arguments to pass to the endpoint
        
    Returns:
        An instance of the endpoint with proxy and headers configured
    """
    api_config = get_api_config()
    
    # Add proxy and headers to kwargs if they're not already present
    if 'proxy' not in kwargs and api_config['proxy']:
        kwargs['proxy'] = api_config['proxy']
    if 'headers' not in kwargs:
        kwargs['headers'] = api_config['headers']
    if 'timeout' not in kwargs:
        kwargs['timeout'] = api_config['timeout']
    
    try:
        endpoint = endpoint_class(**kwargs)
        if kwargs.get('proxy'):
            get_proxy_manager().mark_success(kwargs['proxy'])
        return endpoint
    except Exception as e:
        if kwargs.get('proxy'):
            get_proxy_manager().mark_failed(kwargs['proxy'])
        raise 