import logging
import time
from requests.exceptions import Timeout, RequestException
from app.utils.config_utils import API_RATE_LIMIT, RateLimiter
from app.utils.fetch.api_utils import get_api_config, create_api_endpoint

logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(max_requests=30, interval=25)

class BaseFetcher:
    """Base class for all fetchers with common functionality."""
    
    def __init__(self):
        self.api_config = get_api_config()
        self.retries = 3
        self.default_timeout = 120  # Increased default timeout

    def _handle_api_call(self, api_call_func, *args, **kwargs):
        """Generic method to handle API calls with retries and rate limiting."""
        last_exception = None

        for attempt in range(self.retries):
            try:
                rate_limiter.wait_if_needed()
                return api_call_func(*args, **kwargs)
            except (Timeout, RequestException) as e:
                last_exception = e
                wait_time = min(2 ** (attempt + 1), 60)  # Exponential backoff, max 60 seconds
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.retries}): {str(e)}. "
                    f"Retrying in {wait_time} seconds..."
                )
                if attempt < self.retries - 1:
                    time.sleep(wait_time)
                    continue
            except Exception as e:
                logger.error(f"Unexpected error in API call: {str(e)}")
                raise

        logger.error(f"All retry attempts failed. Last error: {str(last_exception)}")
        raise last_exception

    def create_endpoint(self, endpoint_class, **kwargs):
        """
        Create an NBA API endpoint with proper configuration and retry handling.
        This method now uses _handle_api_call for retries.
        """
        def _create_endpoint():
            # Create the endpoint without timeout in kwargs
            endpoint = create_api_endpoint(endpoint_class, **kwargs)
            # Test the endpoint connection
            try:
                endpoint.get_dict()
            except Exception as e:
                logger.warning(f"Endpoint validation failed: {str(e)}")
                raise
            return endpoint

        return self._handle_api_call(_create_endpoint)

    @staticmethod
    def normalize_keys(data, lowercase=True):
        """Normalize dictionary keys (e.g., convert to lowercase)."""
        if not isinstance(data, dict):
            return data
        return {
            k.lower() if lowercase else k: BaseFetcher.normalize_keys(v, lowercase)
            for k, v in data.items()
        } 