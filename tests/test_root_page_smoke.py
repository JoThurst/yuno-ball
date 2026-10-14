import os

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app import create_app
from tests.config import TestConfig


def test_root_page_renders_welcome_content():
    app = create_app(TestConfig)
    app.config.update(TESTING=True, IS_LOCAL=True, FORCE_HTTPS=False)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"Welcome to Yuno Ball" in response.data
