from datetime import datetime, timedelta
import random
from app.utils.config_utils import PROXY_LIST, logger

# In-memory cache for when Flask context is not available (e.g., standalone scripts)
_in_memory_cache = {}

class ProxyManager:
    def __init__(self):
        self.cache_key_prefix = "proxy_stats:"
        self.max_fails = 5  # Increased max fails before blacklisting
        # Short cooldown so rotating ports can be reused during a daily ingest run
        self.cooldown_period = 2
        self.max_daily_requests = 5000  # Maximum requests per proxy per day
        self._has_flask_context = self._check_flask_context()
        
        # Initialize proxy stats in cache if not exists
        for proxy in PROXY_LIST:
            key = f"{self.cache_key_prefix}{proxy}"
            if not self._get_cache(key):
                self._init_proxy_stats(proxy)

    def _check_flask_context(self):
        """Check if Flask application context is available."""
        try:
            from flask import has_app_context, current_app
            return has_app_context() and hasattr(current_app, 'redis')
        except (ImportError, RuntimeError):
            return False

    def _get_cache(self, key):
        """Safe wrapper for getting cache data - works with or without Flask context."""
        if self._has_flask_context:
            try:
                from flask import current_app
                cached_data = current_app.redis.get(key)
                if cached_data is None:
                    return None
                try:
                    return eval(cached_data)  # Convert string representation back to dict
                except:
                    return cached_data
            except (RuntimeError, AttributeError):
                # Flask context lost, fall back to in-memory
                self._has_flask_context = False
                return _in_memory_cache.get(key)
        else:
            # Use in-memory cache for standalone scripts
            return _in_memory_cache.get(key)

    def _set_cache(self, key, data, ex=86400):
        """Safe wrapper for setting cache data - works with or without Flask context."""
        if self._has_flask_context:
            try:
                from flask import current_app
                current_app.redis.set(key, str(data), ex=ex)
            except (RuntimeError, AttributeError):
                # Flask context lost, fall back to in-memory
                self._has_flask_context = False
                _in_memory_cache[key] = data
        else:
            # Use in-memory cache for standalone scripts
            _in_memory_cache[key] = data

    def _init_proxy_stats(self, proxy):
        stats = {
            'fails': 0,
            'consecutive_fails': 0,  # Track consecutive failures
            'last_used': None,
            'requests_today': 0,
            'last_reset': str(datetime.now().date()),
            'success_rate': 100.0,  # Track success rate
            'total_requests': 0
        }
        self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)

    def get_healthy_proxy(self):
        now = datetime.now()
        available_proxies = []
        proxy_scores = []  # List to store proxy scores for weighted selection

        for proxy in PROXY_LIST:
            stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
            if not stats:
                self._init_proxy_stats(proxy)
                available_proxies.append(proxy)
                proxy_scores.append(100)  # New proxies get full score
                continue

            # Check if stats need daily reset
            last_reset = datetime.strptime(stats['last_reset'], '%Y-%m-%d').date()
            if last_reset < now.date():
                self._init_proxy_stats(proxy)
                available_proxies.append(proxy)
                proxy_scores.append(100)
                continue

            # Check if proxy is healthy
            if (stats['fails'] < self.max_fails and 
                stats['consecutive_fails'] < 3 and  # No more than 2 consecutive fails
                stats['requests_today'] < self.max_daily_requests and
                (stats['last_used'] is None or 
                 (now - datetime.fromisoformat(stats['last_used'])).total_seconds() > self.cooldown_period)):
                
                # Calculate proxy score based on success rate and usage
                score = stats['success_rate'] * (1 - stats['requests_today'] / self.max_daily_requests)
                available_proxies.append(proxy)
                proxy_scores.append(max(score, 1))  # Ensure minimum score of 1

        if not available_proxies:
            logger.warning("No healthy proxies available! Resetting all proxies...")
            self._reset_all_proxies()
            return random.choice(PROXY_LIST)

        # Prefer Decodo residential port 7000 when available (more reliable than sticky ports)
        preferred = [
            (p, s) for p, s in zip(available_proxies, proxy_scores)
            if p.endswith(":7000")
        ]
        if preferred:
            available_proxies, proxy_scores = zip(*preferred)
            available_proxies = list(available_proxies)
            proxy_scores = list(proxy_scores)

        # Use weighted random choice based on proxy scores
        total_score = sum(proxy_scores)
        weights = [score/total_score for score in proxy_scores]
        selected = random.choices(available_proxies, weights=weights, k=1)[0]
        
        # Update proxy stats
        stats = self._get_cache(f"{self.cache_key_prefix}{selected}")
        stats['last_used'] = str(now)
        stats['requests_today'] += 1
        stats['total_requests'] += 1
        self._set_cache(f"{self.cache_key_prefix}{selected}", stats)
        
        return selected

    def mark_failed(self, proxy):
        stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
        if stats:
            stats['fails'] += 1
            stats['consecutive_fails'] += 1
            total_requests = max(stats['total_requests'], 1)
            stats['success_rate'] = ((total_requests - stats['fails']) / total_requests) * 100
            self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)
            logger.warning(f"Proxy {proxy.split('@')[1]} failed. Total fails: {stats['fails']}, Consecutive: {stats['consecutive_fails']}")

    def mark_success(self, proxy):
        stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
        if stats:
            stats['consecutive_fails'] = 0  # Reset consecutive failures
            total_requests = stats['total_requests']
            stats['success_rate'] = ((total_requests - stats['fails']) / total_requests) * 100
            self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)

    def _reset_all_proxies(self):
        """Reset all proxy stats when no healthy proxies are available"""
        logger.info("Resetting all proxy stats...")
        for proxy in PROXY_LIST:
            self._init_proxy_stats(proxy)
            # Add a small random delay before making the proxy available
            stats = self._init_proxy_stats(proxy)
            stats['last_used'] = str(datetime.now() - timedelta(seconds=random.randint(0, 300)))
            self._set_cache(f"{self.cache_key_prefix}{proxy}", stats) 