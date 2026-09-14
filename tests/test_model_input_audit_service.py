"""Tests for the read-only Program G model-input audit."""

from datetime import date, datetime, timezone

from app.services.model_input_audit_service import audit_model_inputs


def _row(team_id: int, *, game_id: str = "g1", feature_as_of=None, **extra):
    return {
        "game_id": game_id,
        "team_id": team_id,
        "game_date": date(2025, 3, 3),
        "scheduled_tipoff": datetime(2025, 3, 3, 23, tzinfo=timezone.utc),
        "feature_as_of": feature_as_of or datetime(2025, 3, 3, 15, tzinfo=timezone.utc),
        "data_available_at": datetime(2025, 3, 3, 15, tzinfo=timezone.utc),
        "source_latest_game_date": date(2025, 3, 1),
        "net_rtg_season": 1.0,
        "season_games_used": 50,
        "net_rtg_lastn": 2.0,
        "window_games_used": 10,
        "days_rest": 2,
        "is_b2b": False,
        "is_3_in_4": False,
        "is_4_in_5": False,
        "is_5_in_7": False,
        "pace_season": 100.0,
        "pace_lastn": 101.0,
        "efg_season": 0.5,
        "efg_lastn": 0.51,
        "tov_pct_season": 0.12,
        "tov_pct_lastn": 0.11,
        "orb_pct_season": 0.2,
        "orb_pct_lastn": 0.21,
        "ftr_season": 0.18,
        "ftr_lastn": 0.19,
        "pct_pts_3pt_season": 0.35,
        "pct_pts_3pt_lastn": 0.36,
        **extra,
    }


def test_paired_cutoff_safe_rows_are_ready_for_baseline_experiment():
    report = audit_model_inputs(
        season="2024-25",
        season_type="Regular Season",
        team_rows=[_row(1), _row(2)],
        environment_rows=[_row(0)],
        outcome_rows=[{"game_id": "g1", "team_id": 1}, {"game_id": "g1", "team_id": 2}],
    )

    assert report["status"] == "ready_for_baseline_experiment"
    assert report["eligible_games"] == 1
    assert report["games_with_outcomes"] == 1
    assert report["violations"] == {
        "missing_pregame_timestamps": 0,
        "feature_after_tipoff": 0,
        "data_available_after_feature": 0,
        "source_latest_game_not_prior": 0,
        "forbidden_target_fields": 0,
    }


def test_empty_current_season_is_explicitly_blocked():
    report = audit_model_inputs(
        season="2026-27",
        season_type="Regular Season",
        team_rows=[],
        environment_rows=[],
        outcome_rows=[],
    )

    assert report["status"] == "blocked_no_completed_game_evidence"
    assert report["eligible_games"] == 0
    assert report["writes_performed"] is False


def test_post_tipoff_feature_is_an_integrity_block():
    report = audit_model_inputs(
        season="2024-25",
        season_type="Regular Season",
        team_rows=[
            _row(1, feature_as_of=datetime(2025, 3, 4, tzinfo=timezone.utc)),
            _row(2),
        ],
        environment_rows=[_row(0)],
        outcome_rows=[{"game_id": "g1", "team_id": 1}, {"game_id": "g1", "team_id": 2}],
    )

    assert report["status"] == "blocked_integrity"
    assert report["violations"]["feature_after_tipoff"] == 1


def test_missing_required_feature_is_a_separate_gate():
    missing = _row(1)
    missing["pace_lastn"] = None
    report = audit_model_inputs(
        season="2024-25",
        season_type="Regular Season",
        team_rows=[missing, _row(2)],
        environment_rows=[_row(0)],
        outcome_rows=[{"game_id": "g1", "team_id": 1}, {"game_id": "g1", "team_id": 2}],
    )

    assert report["status"] == "blocked_missing_required_features"
    assert report["required_feature_missing"]["pace_lastn"] == 1
    assert report["required_feature_missing_rows"] == 1


def test_latest_selection_prefers_valid_timestamp_over_null_revision():
    missing = _row(1)
    missing["feature_as_of"] = None
    report = audit_model_inputs(
        season="2024-25",
        season_type="Regular Season",
        team_rows=[_row(1), missing, _row(2)],
        environment_rows=[_row(0)],
        outcome_rows=[{"game_id": "g1", "team_id": 1}, {"game_id": "g1", "team_id": 2}],
    )

    assert report["status"] == "ready_for_baseline_experiment"
    assert report["violations"]["missing_pregame_timestamps"] == 0
