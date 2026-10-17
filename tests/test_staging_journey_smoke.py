import json

from scripts.staging_journey_smoke import MatchupSpec, main, run_smoke


class FakeResponse:
    def __init__(self, status_code=200, *, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path, *, allow_redirects=False):
        self.calls.append((path, allow_redirects))
        return self.responses[path]


def _payload(target_date, *, game_id, state, actual=None):
    return {
        "target_date": target_date,
        "status": "available",
        "games": [{
            "game_id": game_id,
            "state": state,
            "away": {"abbreviation": "AWY"},
            "home": {"abbreviation": "HOM"},
            "actual": actual,
        }],
        "freshness": {"status": "fresh"},
    }


def _transport():
    return FakeTransport({
        "/daily/api/v1?date=2025-03-03&season=2024-25": FakeResponse(payload=_payload("2025-03-03", game_id="scheduled-game", state="scheduled")),
        "/daily/api/v1?date=2025-03-04&season=2024-25": FakeResponse(payload=_payload("2025-03-04", game_id="final-game", state="completed", actual={"status": "final"})),
        "/daily/2025-03-03?season=2024-25": FakeResponse(text='<a href="/daily/archive?season=2024-25">Archive</a><a href="/matchup/2025-03-03/AWY-HOM?season=2024-25">Open</a>'),
        "/daily/2025-03-04?season=2024-25": FakeResponse(text='<a href="/daily/archive?season=2024-25">Archive</a><a href="/matchup/2025-03-04/AWY-HOM?season=2024-25">Open</a>'),
        "/daily/api/v1?date=2025-07-01&season=2024-25": FakeResponse(payload={"target_date": "2025-07-01", "status": "empty", "games": [], "freshness": {"status": "unknown"}}),
        "/daily/api/v1?date=2025-07-02&season=2024-25": FakeResponse(payload={"target_date": "2025-07-02", "status": "available", "games": [], "freshness": {"status": "stale", "is_stale": True}}),
        "/daily/2025-07-01?season=2024-25": FakeResponse(text="<div>NO SLATE</div><h2>No game context is available for this date.</h2>"),
        "/daily/2025-07-02?season=2024-25": FakeResponse(text='<div class="di-freshness di-freshness-stale"><strong>STALE</strong></div>'),
        "/matchup/2025-03-03/AWY-HOM?season=2024-25": FakeResponse(text="scheduled-game"),
        "/matchup/2025-03-04/AWY-HOM?season=2024-25": FakeResponse(text="final-game"),
        "/daily/archive?season=2024-25": FakeResponse(text='<a href="/daily/2024-12-01?season=2024-25">Date</a>'),
        "/daily/2024-12-01?season=2024-25": FakeResponse(
            text='<a href="/matchup/2024-12-01/AWY-HOM?season=2024-25">Archived matchup</a>'
        ),
        "/daily/api/v1?date=2024-12-01&season=2024-25": FakeResponse(
            payload=_payload("2024-12-01", game_id="archive-game", state="completed", actual={"status": "final"})
        ),
        "/daily/?date=2025-03-03&season=2024-25": FakeResponse(302, headers={"Location": "/daily/2025-03-03?season=2024-25"}),
        "/home?date=2025-03-03&season=2024-25": FakeResponse(302, headers={"Location": "/daily/2025-03-03?season=2024-25"}),
        "/dashboard/": FakeResponse(404),
        "/design/status": FakeResponse(404),
        "/design/daily-v1": FakeResponse(404),
        "/daily/betting": FakeResponse(404),
        "/health/ready": FakeResponse(payload={
            "status": "degraded_ready",
            "dependencies": {"postgresql": "ok", "redis": "unavailable"},
        }),
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
    assert ("/health/ready", False) in transport.calls


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


def test_cli_rejects_other_loopback_base_url(capsys):
    exit_code = main([
        "--base-url", "http://127.0.0.2:8000",
        "--date", "2025-03-03", "--date", "2025-03-04",
        "--scheduled-matchup", "2025-03-03/AWY-HOM",
        "--final-matchup", "2025-03-04/AWY-HOM",
        "--empty-date", "2025-07-01",
        "--stale-date", "2025-07-02",
    ])
    assert exit_code == 2
    assert "localhost" in capsys.readouterr().out


def test_cli_rejects_nonseason_input_without_echoing_it(capsys):
    exit_code = main([
        "--base-url", "https://staging.example.test",
        "--date", "2025-03-03", "--date", "2025-03-04",
        "--scheduled-matchup", "2025-03-03/AWY-HOM",
        "--final-matchup", "2025-03-04/AWY-HOM",
        "--empty-date", "2025-07-01",
        "--stale-date", "2025-07-02",
        "--season", "credential-like-input",
    ])
    output = capsys.readouterr().out
    assert exit_code == 2
    assert "--season must use YYYY-YY" in output
    assert "credential-like-input" not in output


def test_smoke_rejects_repeated_game_identity_and_wrong_final_contract():
    transport = _transport()
    transport.responses["/daily/api/v1?date=2025-03-04&season=2024-25"] = FakeResponse(
        payload=_payload(
            "2025-03-04",
            game_id="scheduled-game",
            state="completed",
            actual={"status": "scheduled"},
        )
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    failed_names = {check.name for check in checks if not check.passed}
    assert "final matchup identity" in failed_names
    assert "distinct date game identities" in failed_names


def test_smoke_rejects_missing_daily_link_and_wrong_matchup_page_identity():
    transport = _transport()
    transport.responses["/daily/2025-03-03?season=2024-25"] = FakeResponse(text="no matchup link")
    transport.responses["/matchup/2025-03-03/AWY-HOM?season=2024-25"] = FakeResponse(text="wrong game")
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    failed_names = {check.name for check in checks if not check.passed}
    assert "scheduled matchup link" in failed_names
    assert "scheduled matchup page identity" in failed_names


def test_smoke_rejects_offsite_daily_links():
    transport = _transport()
    transport.responses["/daily/2025-03-03?season=2024-25"] = FakeResponse(
        text=(
            '<a href="https://other.example/daily/archive?season=2024-25">Archive</a>'
            '<a href="https://other.example/matchup/2025-03-03/AWY-HOM?season=2024-25">Open</a>'
        )
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    failed_names = {check.name for check in checks if not check.passed}
    assert "date page archive link" in failed_names
    assert "scheduled matchup link" in failed_names


def test_smoke_rejects_missing_rendered_empty_and_stale_states():
    transport = _transport()
    transport.responses["/daily/2025-07-01?season=2024-25"] = FakeResponse(text="generic page")
    transport.responses["/daily/2025-07-02?season=2024-25"] = FakeResponse(
        text='<div class="di-freshness di-freshness-fresh"><strong>FRESH</strong></div>'
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    failed_names = {check.name for check in checks if not check.passed}
    assert "empty state visible" in failed_names
    assert "stale state visible" in failed_names


def test_smoke_rejects_archive_without_a_rendered_date_destination():
    transport = _transport()
    transport.responses["/daily/archive?season=2024-25"] = FakeResponse(
        text='<a href="/daily/archive?season=2024-25">Archive</a>'
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    assert any(
        check.name == "archive date link" and not check.passed
        for check in checks
    )


def test_smoke_rejects_offsite_archive_date_link():
    transport = _transport()
    transport.responses["/daily/archive?season=2024-25"] = FakeResponse(
        text='<a href="https://other.example/daily/2024-12-01?season=2024-25">Date</a>'
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    assert any(
        check.name == "archive date link" and not check.passed
        for check in checks
    )


def test_smoke_rejects_redirected_or_empty_archive_date_destination():
    transport = _transport()
    transport.responses["/daily/2024-12-01?season=2024-25"] = FakeResponse(
        302,
        headers={"Location": "/daily/2024-12-02?season=2024-25"},
    )
    transport.responses["/daily/api/v1?date=2024-12-01&season=2024-25"] = FakeResponse(
        payload={
            "target_date": "2024-12-01",
            "status": "empty",
            "games": [],
            "freshness": {"status": "unknown"},
        }
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    failed_names = {check.name for check in checks if not check.passed}
    assert "archive date destination" in failed_names
    assert "archive date page identity" in failed_names
    assert "archive date identity" in failed_names
    assert ("/daily/2024-12-01?season=2024-25", False) in transport.calls


def test_smoke_rejects_archive_date_page_without_linked_date_matchup():
    transport = _transport()
    transport.responses["/daily/2024-12-01?season=2024-25"] = FakeResponse(
        text='<a href="/matchup/2024-12-01/BOG-US?season=2024-25">Wrong game</a>'
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    assert any(
        check.name == "archive date page identity" and not check.passed
        for check in checks
    )


def test_smoke_rejects_redirected_ordinary_probe():
    transport = _transport()
    transport.responses["/design/status"] = FakeResponse(
        302, headers={"Location": "/missing"}
    )
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    assert any(
        check.name == "production route restriction"
        and check.path == "/design/status"
        and not check.passed
        for check in checks
    )
    assert ("/design/status", False) in transport.calls


def test_smoke_rejects_incoherent_readiness_dependencies():
    transport = _transport()
    transport.responses["/health/ready"] = FakeResponse(payload={
        "status": "ready",
        "dependencies": {"postgresql": "ok", "redis": "unavailable"},
    })
    checks = run_smoke(
        transport,
        dates=("2025-03-03", "2025-03-04"),
        scheduled=MatchupSpec.parse("2025-03-03/AWY-HOM"),
        final=MatchupSpec.parse("2025-03-04/AWY-HOM"),
        empty_date="2025-07-01",
        stale_date="2025-07-02",
        season="2024-25",
    )
    assert any(check.name == "readiness dependencies" and not check.passed for check in checks)


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
