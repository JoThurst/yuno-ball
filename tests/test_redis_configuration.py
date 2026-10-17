"""Redis clients must follow the configured environment URL."""

import os

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from tests.config import TestConfig


def test_app_configures_redis_from_the_selected_config():
    class RedisConfig(TestConfig):
        REDIS_URL = "redis://cache.internal:6381/2"

    app = create_app(RedisConfig)
    connection = app.redis.connection_pool.connection_kwargs

    assert connection["host"] == "cache.internal"
    assert connection["port"] == 6381
    assert connection["db"] == 2
    assert connection["socket_connect_timeout"] == 1
    assert connection["socket_timeout"] == 1
