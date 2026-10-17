"""Contract tests for Kaggle game parsing and staging gates."""

from __future__ import annotations

from unittest.mock import MagicMock
import uuid

import pytest

from scripts.import_kaggle_games import (
    EXPECTED_HEADER,
    KaggleGameParseError,
    parse_kaggle_games,
)
from app.services.kaggle_game_staging_service import _eligible_manifest


def _csv_row(**overrides):
    values = {
        "game_id": "0021200001",
        "game_date": "2012-10-30",
        "matchup": "AAA vs. BBB",
        "team_id": "1",
        "is_home": "t",
        "wl": "W",
        "w": "1",
        "l": "0",
        "w_pct": "1",
        "min": "240",
        "fgm": "40",
        "fga": "80",
        "fg_pct": "0.5",
        "fg3m": "8",
        "fg3a": "20",
        "fg3_pct": "0.4",
        "ftm": "12",
        "fta": "15",
        "ft_pct": "0.8",
        "oreb": "10",
        "dreb": "30",
        "reb": "40",
        "ast": "20",
        "stl": "5",
        "blk": "4",
        "tov": "10",
        "pf": "18",
        "pts": "100",
        "a_team_id": "2",
        "season_year": "2012",
        "season_type": "Regular Season",
        "season": "2012-13",
    }
    values.update(overrides)
    return ",".join(values[field] for field in EXPECTED_HEADER)


def _write_pair(tmp_path, first=None, second=None):
    source = tmp_path / "games.csv"
    second_values = {
        "matchup": "BBB @ AAA",
        "team_id": "2",
        "is_home": "f",
        "wl": "L",
        "a_team_id": "1",
    }
    second_values.update(second or {})
    source.write_text(
        ",".join(EXPECTED_HEADER)
        + "\n"
        + _csv_row(**(first or {}))
        + "\n"
        + _csv_row(**second_values)
        + "\n",
        encoding="utf-8",
    )
    return source


def test_parser_stages_paired_game_and_preserves_typed_missingness(tmp_path):
    source = _write_pair(tmp_path, first={"fg3_pct": ""}, second={"ft_pct": ""})

    parsed = parse_kaggle_games(source)

    assert parsed.source_row_count == 2
    assert parsed.distinct_games == 1
    assert parsed.rejections == ()
    assert parsed.rows[0]["fg3_pct"] is None
    assert parsed.rows[1]["ft_pct"] is None
    assert parsed.rows[0]["promotion_eligibility"] == "eligible_market_range"
    assert parsed.rows[0]["canonical_match_status"] == "not_evaluated"


def test_parser_preserves_cancelled_pair_without_inventing_result(tmp_path):
    source = _write_pair(
        tmp_path,
        first={"wl": "", "pts": "0"},
        second={"wl": "", "pts": "0"},
    )

    parsed = parse_kaggle_games(source)

    assert len(parsed.rows) == 2
    assert {row["wl"] for row in parsed.rows} == {None}
    assert {row["result_status"] for row in parsed.rows} == {"missing"}
    assert {row["promotion_eligibility"] for row in parsed.rows} == {
        "excluded_incomplete_result"
    }


def test_parser_quarantines_both_sides_of_invalid_pair(tmp_path):
    source = _write_pair(tmp_path, second={"a_team_id": "3"})

    parsed = parse_kaggle_games(source)

    assert parsed.rows == ()
    assert len(parsed.rejections) == 2
    assert parsed.rejection_counts == {"invalid_game_pair": 2}


def test_parser_rejects_header_drift(tmp_path):
    source = tmp_path / "games.csv"
    source.write_text("game_id,team_id\n1,2\n", encoding="utf-8")

    with pytest.raises(KaggleGameParseError, match="Unexpected CSV header"):
        parse_kaggle_games(source)


def test_manifest_gate_requires_registered_game_artifact():
    session = MagicMock()
    manifest = MagicMock()
    manifest.source_name = "kaggle-uploaded-pack"
    manifest.dataset_name = "nba-team-game-facts"
    manifest.file_name = "nba_games_all.csv"
    manifest.sha256 = "a" * 64
    manifest.source_row_count = 2
    manifest.license_status = "approved_public"
    manifest.commercial_use_status = "permitted"
    manifest.validation_status = "registered"
    session.get.return_value = manifest

    assert _eligible_manifest(
        session,
        source_import_id=str(uuid.uuid4()),
        file_name="nba_games_all.csv",
        file_sha256="a" * 64,
        source_row_count=2,
    ) is manifest

    manifest.dataset_name = "wrong-dataset"
    with pytest.raises(ValueError, match="dataset_name"):
        _eligible_manifest(
            session,
            source_import_id=str(uuid.uuid4()),
            file_name="nba_games_all.csv",
            file_sha256="a" * 64,
            source_row_count=2,
        )
