"""Test real Flask tracing middleware without a separately running server."""
import pytest
from app import create_app
from tests.config import TestConfig

pytestmark = pytest.mark.integration

@pytest.fixture
def tracing_client():
    app = create_app(TestConfig)
    app.config.update(TESTING=True, FORCE_HTTPS=False, IS_LOCAL=True)
    @app.get('/_test/tracing')
    def fixture_response():
        return {'ok': True}
    return app.test_client()

def test_request_tracing(tracing_client):
    response = tracing_client.get('/_test/tracing')
    assert response.status_code == 200
    assert response.headers['X-Request-ID']

def test_request_tracing_on_error(tracing_client):
    response = tracing_client.get('/api/nonexistent')
    assert response.status_code == 404
    assert response.json['request_id'] == response.headers['X-Request-ID']

def test_request_tracing_preserves_supplied_id(tracing_client):
    response = tracing_client.get('/_test/tracing', headers={'X-Request-ID': 'fixture-request'})
    assert response.headers['X-Request-ID'] == 'fixture-request'
