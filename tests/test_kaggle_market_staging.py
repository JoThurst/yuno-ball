"""Contract tests for historical Kaggle market parsing and atomic scope."""

from __future__ import annotations

import uuid

import pytest

from scripts.import_kaggle_markets import (
    KaggleMarketParseError,
    parse_market_artifact,
)
from app.services.kaggle_market_staging_service import stage_kaggle_markets


def test_moneyline_parser_quarantines_both_positive_prices(tmp_path):
    source = tmp_path / "money.csv"
    source.write_text(
        "game_id,book_name,book_id,team_id,a_team_id,price1,price2\n"
        "0021200001,Book,1,10,20,-110,100\n"
        "0021200002,Book,1,10,20,120,130\n",
        encoding="utf-8",
    )

    parsed = parse_market_artifact("moneyline", source)

    assert parsed.source_row_count == 2
    assert len(parsed.rows) == 1
    assert len(parsed.anomalies) == 1
    assert parsed.rejections == ()
    assert parsed.anomalies[0]["reason_code"] == "both_moneyline_prices_positive"
    assert parsed.rows[0]["timing_precision"] == "unknown"
    assert parsed.rows[0]["snapshot_type"] == "historical_static"


def test_spread_parser_preserves_selection_specific_lines_and_quarantines_price(tmp_path):
    source = tmp_path / "spread.csv"
    source.write_text(
        "game_id,book_name,book_id,team_id,a_team_id,spread1,spread2,price1,price2\n"
        "0021200001,Book,1,10,20,7.5,-7,-110,-110\n"
        "0021200002,Book,1,10,20,2,-2,856,-1056\n",
        encoding="utf-8",
    )

    parsed = parse_market_artifact("spread", source)

    assert len(parsed.rows) == 1
    assert parsed.rows[0]["line_pair_status"] == "selection_specific"
    assert parsed.selection_specific_pairs == 1
    assert parsed.anomalies[0]["reason_code"] == "extreme_spread_price"


def test_total_parser_preserves_different_selection_lines_and_quarantines_range(tmp_path):
    source = tmp_path / "total.csv"
    source.write_text(
        "game_id,book_name,book_id,team_id,a_team_id,total1,total2,price1,price2\n"
        "0021200001,Book,1,10,20,210,210.5,-110,-110\n"
        "0021200002,Book,1,10,20,98,198,-110,-110\n",
        encoding="utf-8",
    )

    parsed = parse_market_artifact("total", source)

    assert len(parsed.rows) == 1
    assert parsed.rows[0]["line_pair_status"] == "selection_specific"
    assert parsed.anomalies[0]["reason_code"] == "total_outside_initial_range"


def test_market_parser_rejects_duplicate_grain_and_header_drift(tmp_path):
    source = tmp_path / "money.csv"
    source.write_text(
        "game_id,book_name,book_id,team_id,a_team_id,price1,price2\n"
        "0021200001,Book,1,10,20,-110,100\n"
        "0021200001,Book,1,10,20,-105,105\n",
        encoding="utf-8",
    )
    parsed = parse_market_artifact("moneyline", source)
    assert len(parsed.rows) == 1
    assert parsed.rejection_counts == {"duplicate_natural_key": 1}

    source.write_text("game_id,book_id\n1,2\n", encoding="utf-8")
    with pytest.raises(KaggleMarketParseError, match="Unexpected moneyline header"):
        parse_market_artifact("moneyline", source)


def test_market_service_requires_all_three_artifacts_before_database_access():
    with pytest.raises(ValueError, match="must be staged together"):
        stage_kaggle_markets(
            source_run_id=str(uuid.uuid4()),
            game_manifest_id=str(uuid.uuid4()),
            market_manifests={
                "moneyline": str(uuid.uuid4()),
                "spread": str(uuid.uuid4()),
            },
            artifacts={"moneyline": object(), "spread": object()},
        )
