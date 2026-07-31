from datetime import datetime, timezone

from app.services import official_availability_slate_service as slate_availability


def test_game_payload_uses_scheduled_tipoff_cutoff_and_preserves_reasons(monkeypatch):
    seen = {}

    def fake_get(game_id, *, cutoff, db):
        seen.update(game_id=game_id, cutoff=cutoff, db=db)
        return {
            "as_of": "2026-04-12T19:00:00+00:00",
            "source": "official_nba",
            "completeness": "complete",
            "observations": [
                {
                    "observation_id": "obs-1",
                    "game_date": "2026-04-12",
                    "matchup": "DAL@CHA",
                    "player_id": 123,
                    "reported_player_name": "Example, Player",
                    "team_id": 1,
                    "game_id": "0022500001",
                    "status": "Questionable",
                    "reason_category": "Injury/Illness",
                    "reason_detail": "Right ankle",
                    "raw_reason": "Injury/Illness - Right ankle",
                    "source_url": "https://example.test/report.pdf",
                }
            ],
            "team_submission_statuses": [],
            "stale": False,
            "freshness_status": "not_evaluated",
            "latest_report": {"document_id": "doc-1"},
        }

    monkeypatch.setattr(
        slate_availability,
        "get_cutoff_aware_availability",
        fake_get,
    )
    db = object()
    payload = slate_availability.build_game_official_availability(
        "0022500001",
        scheduled_tipoff=datetime(2026, 4, 12, 20, 0),
        db=db,
    )

    assert seen["game_id"] == "0022500001"
    assert seen["cutoff"] == datetime(2026, 4, 12, 20, 0, tzinfo=timezone.utc)
    assert seen["db"] is db
    assert payload["completeness"] == "complete"
    assert payload["observations"][0]["reason_detail"] == "Right ankle"
    assert payload["observations"][0]["identity_status"] == "resolved"
    assert payload["latest_report"] == {"document_id": "doc-1"}


def test_empty_player_evidence_does_not_become_healthy(monkeypatch):
    monkeypatch.setattr(
        slate_availability,
        "get_cutoff_aware_availability",
        lambda *args, **kwargs: {
            "as_of": None,
            "source": None,
            "observations": [],
            "team_submission_statuses": [
                {"submission_status": "NOT YET SUBMITTED", "team_id": 1}
            ],
            "missing_reason": "no_official_report_before_cutoff",
        },
    )

    payload = slate_availability.build_game_official_availability(
        "0022500001",
        scheduled_tipoff=datetime(2026, 4, 12, 20, 0, tzinfo=timezone.utc),
        db=object(),
    )

    assert payload["completeness"] == "unknown"
    assert payload["unknown_reason"] == "team_submission_only"
    assert payload["team_submission_statuses"][0]["submission_status"] == "NOT YET SUBMITTED"


def test_non_available_rows_are_team_scoped_and_available_is_not_a_callout():
    payload = {
        "observations": [
            {"team_id": 1, "status": "Out", "player_id": 10},
            {"team_id": 1, "status": "Available", "player_id": 11},
            {"team_id": 2, "status": "Questionable", "player_id": 12},
        ]
    }

    assert slate_availability.non_available_observations(payload, team_id=1) == [
        {"team_id": 1, "status": "Out", "player_id": 10}
    ]
    assert slate_availability.non_available_observations(payload, team_id=2) == [
        {"team_id": 2, "status": "Questionable", "player_id": 12}
    ]
