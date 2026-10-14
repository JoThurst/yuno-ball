"""Public Daily errors must not echo connection or provider details."""

import os

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from tests.config import TestConfig


def test_daily_html_hides_internal_failure(monkeypatch):
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)

    def fail(**_kwargs):
        raise RuntimeError("DATABASE_URL=secret-host/internal-detail")

    monkeypatch.setattr("app.services.daily_intelligence_service.build_daily_intelligence_v1", fail)
    response = app.test_client().get("/daily/2025-04-12")

    assert response.status_code == 500
    assert b"temporarily unavailable" in response.data
    assert b"secret-host" not in response.data


def test_daily_api_hides_internal_failure(monkeypatch):
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)

    def fail(**_kwargs):
        raise RuntimeError("DATABASE_URL=secret-host/internal-detail")

    monkeypatch.setattr("app.services.daily_intelligence_service.build_daily_intelligence_v1", fail)
    response = app.test_client().get("/daily/api/v1?date=2025-04-12")

    assert response.status_code == 500
    assert response.get_json() == {"error": "DAILY_INTELLIGENCE_UNAVAILABLE"}
