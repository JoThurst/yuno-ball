from flask import Flask, jsonify

from app.middleware.security import secure_endpoint, validate_season


def _client(*, testing):
    app = Flask(__name__)
    app.config.update(TESTING=testing, IS_LOCAL=False, FORCE_HTTPS=False)

    @app.get('/season')
    @secure_endpoint()
    def season():
        return jsonify(ok=True)

    return app.test_client()


def test_validate_season_accepts_current_and_future_canonical_seasons():
    assert validate_season('2025-26')
    assert validate_season('2026-27')


def test_validate_season_rejects_malformed_or_nonconsecutive_seasons():
    assert not validate_season('2026-7')
    assert not validate_season('2026-28')
    assert not validate_season('2009-10')


def test_testing_mode_does_not_bypass_season_validation():
    response = _client(testing=True).get('/season?season=2026-28')

    assert response.status_code == 400
    assert response.get_json() == {'error': 'Invalid season format'}


def test_production_mode_accepts_current_season():
    response = _client(testing=False).get('/season?season=2026-27')

    assert response.status_code == 200
    assert response.get_json() == {'ok': True}
