import os
from unittest.mock import patch

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from flask import render_template
from tests.config import TestConfig


def test_rendered_status_page_does_not_fetch_live_matchups_for_navbar():
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)

    with patch(
        "app.models.gameschedule_sqlalchemy.GameScheduleORM.get_by_date",
        return_value=[],
    ), patch(
        "app.services.dashboard_service.fetch_todays_games",
        side_effect=AssertionError("navbar must not fetch live games"),
    ):
        response = app.test_client().get("/design/status")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Daily Intelligence V1" in body


def test_base_template_has_accessible_loader_failsafe():
    app = create_app(TestConfig)
    with app.test_request_context("/"):
        body = render_template("base.html")

    assert 'aria-label="Loading Yuno Ball"' in body
    assert "window.setTimeout(releasePageLoader, 2500)" in body
