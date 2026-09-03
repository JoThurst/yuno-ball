"""Regression tests for proxy pool recovery."""

from unittest.mock import patch

from app.utils.fetch.proxy_manager import ProxyManager, _in_memory_cache


def test_proxy_pool_reset_reinitializes_stats_without_none_error():
    proxies = [
        "http://user:password@proxy.test:10001",
        "http://user:password@proxy.test:10002",
    ]
    _in_memory_cache.clear()
    try:
        with patch("app.utils.fetch.proxy_manager.PROXY_LIST", proxies):
            manager = ProxyManager()
            manager._reset_all_proxies()

            for proxy in proxies:
                stats = manager._get_cache(f"proxy_stats:{proxy}")
                assert stats is not None
                assert stats["requests_today"] == 0
                assert stats["last_used"] is not None
    finally:
        _in_memory_cache.clear()
