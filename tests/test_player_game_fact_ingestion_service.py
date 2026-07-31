from datetime import date, datetime, timezone

import pytest

from app.services.traditional_boxscore_v3_adapter import reconcile_player_totals, transform_payload


def _payload():
    return {
        "player_stats": {"headers": ["PLAYER_ID", "TEAM_ID", "MIN", "PTS", "PLAYER_STATUS"],
                         "data": [[7, 1, "0:00", None, "DNP"], [8, 1, "12:34", 9, None],
                                  [9, 2, "20:00", 12, None]]},
        "team_stats": {"headers": ["TEAM_ID", "PTS"], "data": [[1, 9], [2, 12]]},
    }


def test_reconcile_player_totals_requires_both_reciprocal_team_rows():
    facts = transform_payload(_payload(), game_id="g", game_date=date(2026, 3, 3),
                              season="2025-26", season_type="Regular Season", run_id="r",
                              retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc))
    assert reconcile_player_totals(_payload(), facts)["total_points"] == 21


def test_reconcile_player_totals_fails_closed_on_mismatch():
    facts = transform_payload(_payload(), game_id="g", game_date=date(2026, 3, 3),
                              season="2025-26", season_type="Regular Season", run_id="r",
                              retrieved_at=datetime(2026, 3, 4, tzinfo=timezone.utc))
    bad = _payload()
    bad["team_stats"]["data"][0][1] = 10
    with pytest.raises(ValueError, match="mismatch"):
        reconcile_player_totals(bad, facts)
