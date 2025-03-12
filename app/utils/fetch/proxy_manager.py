from datetime import datetime
import random
from app.utils.config_utils import PROXY_LIST, logger
from flask import current_app

class ProxyManager:
    def __init__(self):
        self.cache_key_prefix = "proxy_stats:"
        self.max_fails = 3
        self.cooldown_period = 300  # 5 minutes
        
        # Initialize proxy stats in Redis if not exists
        for proxy in PROXY_LIST:
            key = f"{self.cache_key_prefix}{proxy}"
            if not self._get_cache(key):
                self._init_proxy_stats(proxy)

    def _get_cache(self, key):
        """Safe wrapper for getting cache data"""
        cached_data = current_app.redis.get(key)
        if cached_data is None:
            return None
        try:
            return eval(cached_data)  # Convert string representation back to dict
        except:
            return cached_data

    def _set_cache(self, key, data, ex=86400):
        """Safe wrapper for setting cache data"""
        current_app.redis.set(key, str(data), ex=ex)

    def _init_proxy_stats(self, proxy):
        stats = {
            'fails': 0,
            'last_used': None,
            'requests_today': 0,
            'last_reset': str(datetime.now().date())
        }
        self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)

    def get_healthy_proxy(self):
        now = datetime.now()
        available_proxies = []

        for proxy in PROXY_LIST:
            stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
            if not stats:
                self._init_proxy_stats(proxy)
                available_proxies.append(proxy)
                continue

            # Check if stats need daily reset
            last_reset = datetime.strptime(stats['last_reset'], '%Y-%m-%d').date()
            if last_reset < now.date():
                self._init_proxy_stats(proxy)
                available_proxies.append(proxy)
                continue

            # Check if proxy is healthy
            if (stats['fails'] < self.max_fails and 
                (stats['last_used'] is None or 
                 (now - datetime.fromisoformat(stats['last_used'])).total_seconds() > self.cooldown_period)):
                available_proxies.append(proxy)

        if not available_proxies:
            logger.warning("No healthy proxies available!")
            self._reset_all_fails()
            return random.choice(PROXY_LIST)

        selected = random.choice(available_proxies)
        stats = self._get_cache(f"{self.cache_key_prefix}{selected}")
        self._update_proxy_stats(selected, {'last_used': str(now), 'requests_today': stats['requests_today'] + 1})
        return selected

    def mark_failed(self, proxy):
        stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
        if stats:
            stats['fails'] += 1
            self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)
            logger.warning(f"Proxy {proxy.split('@')[1]} failed. Total fails: {stats['fails']}")

    def mark_success(self, proxy):
        stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
        if stats:
            stats['fails'] = 0
            self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)

    def _update_proxy_stats(self, proxy, updates):
        stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
        if stats:
            stats.update(updates)
            self._set_cache(f"{self.cache_key_prefix}{proxy}", stats)

    def _reset_all_fails(self):
        for proxy in PROXY_LIST:
            stats = self._get_cache(f"{self.cache_key_prefix}{proxy}")
            if stats:
                stats['fails'] = 0
                self._set_cache(f"{self.cache_key_prefix}{proxy}", stats) 