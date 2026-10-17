import os

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from app.middleware import rate_limiter
from tests.config import TestConfig


def _production_test_app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("FORCE_LOCAL", "false")
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_PRODUCTION=True, IS_LOCAL=False, FORCE_HTTPS=False)
    return app


def test_beta_hides_internal_and_betting_pages_in_production(monkeypatch):
    app = _production_test_app(monkeypatch)
    client = app.test_client()

    for path in ("/dashboard/", "/design/status", "/daily/betting"):
        assert client.get(path).status_code == 404


def test_beta_navigation_only_links_to_enabled_public_surfaces(monkeypatch):
    app = _production_test_app(monkeypatch)

    with app.test_request_context("/"):
        from flask import render_template

        navigation = render_template("navbar.html", today_matchups=[])

    assert "Daily archive" in navigation
    for label in ("Betting · pilot", "Research console", "Players", "Teams", "Games", "Roadmap status"):
        assert label not in navigation
    assert "function closeMenu(menu)" in navigation


def test_readiness_is_subject_to_production_rate_limit(monkeypatch):
    app = _production_test_app(monkeypatch)
    monkeypatch.setattr(rate_limiter, "get_cache", lambda _key: "60")
    readiness_called = []

    def fail_if_probed(_client):
        readiness_called.append(True)
        return {"postgresql": True, "redis": True}

    monkeypatch.setattr("app.services.readiness_service.check_readiness", fail_if_probed)
    response = app.test_client().get("/health/ready")

    assert response.status_code == 429
    assert readiness_called == []


def test_readiness_has_in_process_limit_when_redis_is_unavailable():
    ip = "203.0.113.12"
    rate_limiter._readiness_hits.pop(ip, None)

    assert all(
        rate_limiter._allow_readiness_probe(ip, now=100 + index)
        for index in range(10)
    )
    assert not rate_limiter._allow_readiness_probe(ip, now=109)
    assert rate_limiter._allow_readiness_probe(ip, now=160)
