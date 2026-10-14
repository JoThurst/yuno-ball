import os
from unittest.mock import MagicMock, Mock

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.services import readiness_service
from tests.config import TestConfig


def _client(monkeypatch, *, postgres=True, redis=True):
    monkeypatch.setattr(readiness_service, "check_postgres_connection", lambda: postgres)
    monkeypatch.setattr(readiness_service, "check_redis_connection", lambda _client: redis)
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)
    return app.test_client()


def test_readiness_reports_available_dependencies(monkeypatch):
    response = _client(monkeypatch).get("/health/ready")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ready",
        "dependencies": {"postgresql": "ok", "redis": "ok"},
    }


def test_readiness_reports_unavailable_dependencies(monkeypatch):
    response = _client(monkeypatch, redis=False).get("/health/ready")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "not_ready",
        "dependencies": {"postgresql": "ok", "redis": "unavailable"},
    }


def test_dependency_probes_hide_secrets_and_bound_postgres_query(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1,)
    connect = Mock(return_value=connection)
    monkeypatch.setattr(readiness_service.psycopg2, "connect", connect)

    assert readiness_service.check_postgres_connection()
    assert connect.call_args.kwargs["connect_timeout"] == 3
    assert connect.call_args.kwargs["options"] == "-c statement_timeout=1500"
    connection.close.assert_called_once()

    redis_client = Mock()
    redis_client.ping.side_effect = RuntimeError("redis password=secret")
    assert readiness_service.check_redis_connection(redis_client) is False
