import json

from scripts.staging_journey_smoke import MatchupSpec, main, run_smoke


class FakeResponse:
    def __init__(self, status_code=200, *, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path, *, allow_redirects=True):
        self.calls.append((path, allow_redirects))
        return self.responses[path]


def _payload(target_date, *, state):
    return {
        "target_date": target_date,
        "status": "available",
        "games": [{
            "game_id": f"game-{target_date}",
            "state": state,
            "away": {"abbreviation": "AWY"},
            "home": {"abbreviation": "HOM"},
        }],
        "freshness": {"status": "fresh"},
    }


def _transport():
    return FakeTransport({
        "/daily/api/v1?date=2025-03-03&season=2024-25": FakeResponse(payload=_payload("2025-03-03", state="scheduled")),
        "/daily/api/v1?date=2025-03-04&season=2024-25": FakeResponse(payload=_payload("2025-03-04", state="final")),
        "/daily/api/v1?date=2025-07-01&season=2024-25": FakeResponse(payload={"target_date": "2025-07-01", "status": "empty", "games": [], "freshness": {"status": "unknown"}}),
        "/daily/api/v1?date=2025-07-02&season=2024-25": FakeResponse(payload={"target_date": "2025-07-02", "status": "available", "games": [], "freshness": {"status": "stale", "is_stale": True}}),
        "/matchup/2025-03-03/AWY-HOM": FakeResponse(),
        "/matchup/2025-03-04/AWY-HOM": FakeResponse(),
        "/daily/archive": FakeResponse(),
        "/daily/?date=2025-03-03&season=2024-25": FakeResponse(302, headers={"Location": "/daily/2025-03-03?season=2024-25"}),
        "/home?date=2025-03-03&season=2024-25": FakeResponse(302, headers={"Location": "/daily/2025-03-03?season=2024-25"}),
        "/dashboard/": FakeResponse(404),
        "/design/status": FakeResponse(404),
        "/design/daily-v1": FakeResponse(404),
        "/daily/betting": FakeResponse(404),
        "/health/ready": FakeResponse(payload={"status": "degraded_ready"}),
    })


def test_smoke_covers_bounded_journey_and_readiness_observation():
    transport = _transport()
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    assert all(check.passed for check in checks), [check.as_dict() for check in checks]
    assert ("/health/ready", True) in transport.calls


def test_cli_rejects_localhost_without_network_access(capsys):
    exit_code = main([
        "--base-url", "http://localhost:8000",
        "--date", "2025-03-03", "--date", "2025-03-04",
        "--scheduled-matchup", "2025-03-03/AWY-HOM",
        "--final-matchup", "2025-03-04/AWY-HOM",
        "--empty-date", "2025-07-01",
        "--stale-date", "2025-07-02",
    ])
    assert exit_code == 2
    assert "localhost" in capsys.readouterr().out


def test_cli_emits_sanitized_json_and_nonzero_on_failed_check(monkeypatch, capsys):
    transport = _transport()
    transport.responses["/design/status"] = FakeResponse(200)
    monkeypatch.setattr("scripts.staging_journey_smoke._commit", lambda: "abc123")
    exit_code = main([
        "--base-url", "https://staging.example.test",
        "--date", "2025-03-03", "--date", "2025-03-04",
        "--scheduled-matchup", "2025-03-03/AWY-HOM",
        "--final-matchup", "2025-03-04/AWY-HOM",
        "--empty-date", "2025-07-01",
        "--stale-date", "2025-07-02",
        "--season", "2024-25",
    ], transport_factory=lambda base_url, timeout: transport)
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["status"] == "FAIL"
    assert output["environment"] == "staging.example.test"
    assert all("password" not in json.dumps(check).lower() for check in output["checks"])
