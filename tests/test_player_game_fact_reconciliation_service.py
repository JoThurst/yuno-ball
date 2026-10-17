from types import SimpleNamespace

from app.services.player_game_fact_reconciliation_service import compare_overlap


def _traditional(**overrides):
    row = {
        "canonical_game_id": "g",
        "canonical_player_id": 10,
        "canonical_team_id": 1,
        "points": 7,
        "assists": 2,
        "rebounds_total": 4,
        "steals": 1,
        "blocks": 0,
        "turnovers": 2,
        "minutes": "10:00",
    }
    row.update(overrides)
    return SimpleNamespace(**row)


def _legacy(**overrides):
    row = {
        "game_id": "g",
        "player_id": 10,
        "team_id": 1,
        "points": 7,
        "assists": 2,
        "rebounds": 4,
        "steals": 1,
        "blocks": 0,
        "turnovers": 2,
        "minutes_played": "10:00",
    }
    row.update(overrides)
    return SimpleNamespace(**row)


def test_compare_overlap_reports_exact_match():
    report = compare_overlap([_traditional()], [_legacy()])
    assert report["overlap_rows"] == 1
    assert report["different_rows"] == 0


def test_compare_overlap_preserves_differences_and_source_only_rows():
    report = compare_overlap(
        [_traditional(), _traditional(canonical_player_id=11)],
        [_legacy(points=8)],
    )
    assert report["traditional_only_rows"] == 1
    assert report["different_rows"] == 1
    assert "points" in report["difference_examples"][0]["fields"]
