from datetime import date, datetime, timezone

from app.services.official_availability_serving_service import (
    build_official_availability_payload,
)


def test_empty_payload_is_unknown_not_healthy():
    payload = build_official_availability_payload(
        [], as_of=datetime(2026, 7, 21, tzinfo=timezone.utc)
    )
    assert payload.completeness == "unknown"
    assert payload.unknown_reason == "no_official_observation"


def test_unresolved_identity_is_partial_and_preserves_nulls():
    payload = build_official_availability_payload(
        [
            {
                "observation_id": "obs-1",
                "game_date": date(2026, 4, 12),
                "matchup_text": "MEM@UTA",
                "player_id": None,
                "reported_player_name": "Key, Tyreke",
                "team_id": 1610612763,
                "game_id": "0022501194",
                "status": "OUT",
                "reason_category": "illness",
                "source_url": "https://example.test/report.pdf",
            }
        ],
        as_of=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    assert payload.completeness == "partial"
    assert payload.observations[0].player_id is None
    assert payload.observations[0].identity_status == "unresolved"
