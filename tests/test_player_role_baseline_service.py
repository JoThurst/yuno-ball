from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.services.player_role_baseline_service import (
    build_pregame_role_baseline,
    build_role_history_observation,
    parse_minutes,
    publish_role_baselines,
    role_history_records_from_facts,
)
from scripts.build_program_h_role_baselines import build_records
from scripts.audit_program_h_source_timing import summarize_source_timing


UTC = timezone.utc


def _fact(index: int, *, minutes="24:00", starter_status="unknown", available_hour=12, available_at=None):
    return {
        "canonical_game_id": f"g{index}",
        "canonical_player_id": 7,
        "canonical_team_id": 1,
        "game_date": date(2025, 3, index),
        "season": "2024-25",
        "season_type": "Regular Season",
        "participation_status": "played",
        "starter_status": starter_status,
        "starter_position": "G" if starter_status == "starter" else None,
        "minutes": minutes,
        "source_name": "nba_boxscore_traditional_v3",
        "fact_id": f"fact-{index}",
        "source_row_sha256": "a" * 64,
        "source_run_id": "run-1",
        "data_available_at": available_at or datetime(2025, 3, index, available_hour, tzinfo=UTC),
    }


def test_parse_minutes_preserves_missing_and_supports_provider_formats():
    assert parse_minutes(None) is None
    assert parse_minutes("12:30") == 12.5
    assert parse_minutes("PT25M01.00S") == 25.02
    assert parse_minutes("24.5") == 24.5


def test_role_baseline_is_strictly_prior_and_cutoff_safe():
    history = [
        build_role_history_observation(_fact(1, minutes="20:00", starter_status="starter")),
        build_role_history_observation(
            _fact(2, minutes="30:00", available_at=datetime(2025, 3, 8, 16, tzinfo=UTC))
        ),
        build_role_history_observation(_fact(3, minutes="24:00")),
        build_role_history_observation(_fact(4, minutes="28:00")),
        build_role_history_observation(_fact(5, minutes="26:00")),
        build_role_history_observation(_fact(6, minutes="40:00")),
        build_role_history_observation(_fact(9, minutes="50:00")),
    ]
    result = build_pregame_role_baseline(
        history,
        canonical_game_id="target",
        canonical_player_id=7,
        canonical_team_id=1,
        target_game_date=date(2025, 3, 8),
        season="2024-25",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 3, 8, 15, tzinfo=UTC),
        source_run_id="run-1",
        window_size=5,
    )

    assert result["completeness_status"] == "complete"
    assert result["played_games_used"] == 5
    assert result["history_games_seen"] == 5
    assert result["baseline_minutes_median"] == 26.0
    assert result["baseline_minutes_high"] == 28.0
    assert result["start_count"] == 1
    assert result["missing_input_flags"] == []
    assert result["timing_policy"] == "strict_source"


def test_unknown_starter_and_missing_minutes_are_not_converted_to_bench_or_zero():
    history = [
        build_role_history_observation(_fact(1, minutes=None)),
        build_role_history_observation(_fact(2, minutes="20:00")),
    ]
    result = build_pregame_role_baseline(
        history,
        canonical_game_id="target",
        canonical_player_id=7,
        canonical_team_id=1,
        target_game_date=date(2025, 3, 3),
        season="2024-25",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 3, 3, 15, tzinfo=UTC),
        source_run_id="run-1",
    )
    assert result["start_count"] == 0
    assert result["baseline_minutes_low"] == 20.0
    assert result["missing_input_flags"] == ["insufficient_prior_played_minutes"]


def test_role_history_records_have_deterministic_ids_and_replay_same_payload():
    first = role_history_records_from_facts([_fact(1, starter_status="starter")])
    replay = role_history_records_from_facts([_fact(1, starter_status="starter")])
    assert first == replay
    assert first[0]["role_history_id"]
    assert first[0]["minutes_decimal"] == 24.0


def test_materializer_skips_date_only_targets_and_keeps_exact_cutoff_targets():
    facts = [SimpleNamespace(**_fact(index)) for index in range(1, 6)]
    exact = SimpleNamespace(
        game_id="target-exact",
        team_id=1,
        game_date=datetime(2025, 3, 8, 19, tzinfo=UTC),
        game_date_precision="exact",
    )
    date_only = SimpleNamespace(
        game_id="target-date-only",
        team_id=1,
        game_date=datetime(2025, 3, 9),
        game_date_precision="date_only",
    )

    history, baselines = build_records(
        facts=facts,
        schedules=[exact, date_only],
        season="2024-25",
        season_type="Regular Season",
        source_run_id="run-1",
        window_size=5,
        max_target_games=10,
    )

    assert len(history) == 5
    assert len(baselines) == 1
    assert baselines[0]["canonical_game_id"] == "target-exact"
    assert baselines[0]["scheduled_tipoff"] == datetime(2025, 3, 8, 19, tzinfo=UTC)


def test_historical_proxy_is_explicitly_unavailable_for_production():
    result = build_pregame_role_baseline(
        [build_role_history_observation(_fact(1, minutes="24:00"))],
        canonical_game_id="target",
        canonical_player_id=7,
        canonical_team_id=1,
        target_game_date=date(2025, 3, 3),
        season="2024-25",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 3, 3, tzinfo=UTC),
        source_run_id="run-1",
        timing_policy="historical_game_date_proxy",
    )
    assert result["data_available_at"] is None
    assert "historical_source_time_unknown" in result["missing_input_flags"]
    assert result["timing_policy"] == "historical_game_date_proxy"


def test_publisher_rejects_historical_proxy_rows_before_database_write():
    try:
        publish_role_baselines(
            [{"timing_policy": "historical_game_date_proxy"}],
            db=object(),
        )
    except ValueError as exc:
        assert "audit-only" in str(exc)
    else:
        raise AssertionError("historical proxy rows must not be publishable")


def test_band_percentiles_are_validated_and_configurable():
    result = build_pregame_role_baseline(
        [build_role_history_observation(_fact(index)) for index in range(1, 6)],
        canonical_game_id="target",
        canonical_player_id=7,
        canonical_team_id=1,
        target_game_date=date(2025, 3, 8),
        season="2024-25",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 3, 8, tzinfo=UTC),
        source_run_id="run-1",
        low_percentile=0.10,
        high_percentile=0.90,
    )
    assert result["baseline_minutes_low"] <= result["baseline_minutes_median"]
    assert result["baseline_minutes_median"] <= result["baseline_minutes_high"]


def test_source_timing_audit_requires_exact_tipoff_and_prior_timestamped_history():
    facts = [
        SimpleNamespace(
            canonical_team_id=1,
            game_date=date(2025, 3, 1),
            canonical_game_id="prior",
            fact_id="fact-1",
            data_available_at=datetime(2025, 3, 2, 15, tzinfo=UTC),
        )
    ]
    schedules = [
        SimpleNamespace(
            team_id=1,
            game_id="exact",
            game_date=datetime(2025, 3, 3, 19, tzinfo=UTC),
            game_date_precision="exact",
        ),
        SimpleNamespace(
            team_id=1,
            game_id="date-only",
            game_date=datetime(2025, 3, 4),
            game_date_precision="date_only",
        ),
    ]

    result = summarize_source_timing(
        facts=facts,
        schedules=schedules,
        season="2024-25",
        season_type="Regular Season",
    )

    assert result["exact_target_team_rows"] == 1
    assert result["exact_targets_with_any_strictly_eligible_history"] == 1
    assert result["eligible_prior_fact_rows"] == 1
    assert result["schedule_precision"] == {"date_only": 1, "exact": 1}
    assert result["strict_source_timing_ready"] is True
    assert result["writes_performed"] is False
