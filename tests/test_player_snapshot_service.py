"""Preservation and cutoff contract tests for Phase 2 player snapshots."""

from datetime import date, datetime, timezone

from app.services.player_snapshot_service import (
    PlayerGameFact,
    build_snapshot_context,
    calculate_snapshot_records,
    feature_cutoff_for_slate,
)


def _game(game_id: str, game_time: datetime, points=20, rebounds=5, assists=5):
    return PlayerGameFact(
        player_id=1,
        player_name="Test Player",
        game_id=game_id,
        team_id=10,
        game_time=game_time,
        points=points,
        rebounds=rebounds,
        assists=assists,
        steals=1,
        blocks=1,
        turnovers=2,
    )


def _context(version="player-v2.1", target=date(2025, 1, 10)):
    return build_snapshot_context(
        season="2024-25",
        target_date=target,
        calculation_version=version,
        source_run_id="00000000-0000-0000-0000-000000000001",
    )


def test_feature_cutoff_is_ten_am_eastern_in_utc():
    assert feature_cutoff_for_slate(date(2025, 1, 10)) == datetime(
        2025, 1, 10, 15, 0, tzinfo=timezone.utc
    )
    assert feature_cutoff_for_slate(date(2025, 7, 10)) == datetime(
        2025, 7, 10, 14, 0, tzinfo=timezone.utc
    )


def test_same_cutoff_and_version_is_deterministic():
    facts = [
        _game("0022400001", datetime(2025, 1, 7, 1, tzinfo=timezone.utc), 10),
        _game("0022400002", datetime(2025, 1, 8, 1, tzinfo=timezone.utc), 20),
        _game("0022400003", datetime(2025, 1, 9, 1, tzinfo=timezone.utc), 30),
        _game("0022400004", datetime(2025, 1, 9, 3, tzinfo=timezone.utc), 25),
        _game("0022400005", datetime(2025, 1, 9, 4, tzinfo=timezone.utc), 15),
    ]
    first = calculate_snapshot_records(facts, _context())
    second = calculate_snapshot_records(facts, _context())
    assert first == second
    assert all(row["feature_as_of"] == _context().feature_as_of for row in first["heat"])


def test_new_calculation_version_has_a_distinct_natural_key():
    facts = [
        _game(f"002240000{i}", datetime(2025, 1, i + 1, 1, tzinfo=timezone.utc), i * 5)
        for i in range(1, 6)
    ]
    old = calculate_snapshot_records(facts, _context("player-v2.1"))
    new = calculate_snapshot_records(facts, _context("player-v2.2"))
    old_key = (
        old["windows"][0]["player_id"],
        old["windows"][0]["feature_as_of"],
        old["windows"][0]["calculation_version"],
    )
    new_key = (
        new["windows"][0]["player_id"],
        new["windows"][0]["feature_as_of"],
        new["windows"][0]["calculation_version"],
    )
    assert old_key != new_key


def test_missing_pra_component_is_not_replaced_with_zero():
    facts = [
        _game("0022400001", datetime(2025, 1, 7, 1, tzinfo=timezone.utc)),
        _game("0022400002", datetime(2025, 1, 8, 1, tzinfo=timezone.utc)),
        _game(
            "0022400003",
            datetime(2025, 1, 9, 1, tzinfo=timezone.utc),
            assists=None,
        ),
        _game("0022400004", datetime(2025, 1, 9, 2, tzinfo=timezone.utc)),
        _game("0022400005", datetime(2025, 1, 9, 3, tzinfo=timezone.utc)),
    ]
    records = calculate_snapshot_records(facts, _context())
    assert not any(row["stat"] == "PRA" for row in records["windows"])
    assert not any(row["stat"] == "PRA" for row in records["heat"])
    assert not any(row["stat_name"] == "pra" for row in records["consistency"])


def test_source_availability_must_precede_feature_cutoff():
    late_fact = _game(
        "0022400001",
        datetime(2025, 1, 10, 13, tzinfo=timezone.utc),
    )
    try:
        calculate_snapshot_records([late_fact], _context())
    except ValueError as exc:
        assert "availability" in str(exc)
    else:
        raise AssertionError("late source fact should make the snapshot ineligible")
