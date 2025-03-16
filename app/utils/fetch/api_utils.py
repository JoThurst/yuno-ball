from app.utils.config_utils import get_proxy, get_headers, logger, PROXY_ENABLED
import os

def get_api_config():
    """
    Returns a dictionary with proxy and headers configuration for NBA API calls.
    
    Returns:
        dict: Configuration with proxy and headers
    """
    # Get proxy and headers
    proxy = get_proxy()
    headers = get_headers()
    
    # Log proxy status
    force_proxy = os.getenv("FORCE_PROXY", "false").lower() == "true"
    force_local = os.getenv("FORCE_LOCAL", "false").lower() == "true"
    
    if proxy:
        logger.info(f"Using proxy for NBA API request (FORCE_PROXY={force_proxy}, FORCE_LOCAL={force_local})")
    else:
        logger.info(f"Using direct connection for NBA API request (FORCE_PROXY={force_proxy}, FORCE_LOCAL={force_local})")
    
    return {
        'proxy': proxy,
        'headers': headers,
        'timeout': 60  # Increased timeout for proxy connections
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
        
    return endpoint_class(**kwargs) 