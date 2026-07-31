from datetime import date, datetime, timezone

from app.services.advanced_boxscore_v3_adapter import transform_advanced_payload


def _payload(comment=""):
    return {
        "boxScoreAdvanced": {
            "gameId": "g",
            "homeTeam": {
                "teamId": 1,
                "players": [
                    {
                        "personId": 10,
                        "comment": comment,
                        "statistics": {
                            "minutes": "10:00" if not comment else "0:00",
                            "usagePercentage": 0.21 if not comment else None,
                            "PIE": 0.12 if not comment else None,
                        },
                    }
                ],
            },
            "awayTeam": {
                "teamId": 2,
                "players": [
                    {
                        "personId": 20,
                        "comment": "",
                        "statistics": {
                            "minutes": "12:00",
                            "trueShootingPercentage": 0.61,
                        },
                    }
                ],
            },
        }
    }


def test_advanced_transform_maps_fields_and_provenance():
    facts = transform_advanced_payload(
        _payload(),
        game_id="g",
        game_date=date(2026, 3, 3),
        season="2025-26",
        season_type="Regular Season",
        run_id="run",
        retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
    )
    assert len(facts) == 2
    assert facts[0]["usage_percentage"] == 0.21
    assert facts[0]["pie"] == 0.12
    assert len(facts[0]["raw_payload"]["response_sha256"]) == 64


def test_advanced_transform_preserves_dnp_nulls():
    fact = transform_advanced_payload(
        _payload("DNP - Coach's Decision"),
        game_id="g",
        game_date=date(2026, 3, 3),
        season="2025-26",
        season_type="Regular Season",
        run_id="run",
        retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc),
    )[0]
    assert fact["participation_status"] == "did_not_play"
    assert fact["usage_percentage"] is None
