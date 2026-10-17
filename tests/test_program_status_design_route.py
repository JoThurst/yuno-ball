import os

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from tests.config import TestConfig


def test_program_status_design_route_renders_all_tracks_and_gate_map():
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)

    response = app.test_client().get("/design/status")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Know what shipped." in body
    assert "Daily Intelligence V1" in body
    assert "2026–27 game bridge" in body
    assert "What unlocks what" in body
    assert "Waiting is explicit" in body
    assert "No service-backed staging run is recorded" in body
    assert "seven tracked roadmap gates" in body
    assert "PENDING" in body
    assert "Odds transport rechecked" in body
    assert "G monitoring rerun" in body
