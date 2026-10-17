from datetime import date, datetime, timezone

import pytest

from app.services.market_observation_service import (
    MarketObservationContractError,
    validate_market_observation,
)


def _header(**overrides):
    value = {
        "source_name": "kaggle_historical_markets",
        "source_observation_key": "import-1:row-10:moneyline:book-a",
        "parser_version": "market-observation-contract-v1",
        "snapshot_type": "historical_static",
        "timing_precision": "unknown",
        "market_type": "moneyline",
        "source_import_id": "import-1",
        "source_run_id": "run-1",
        "source_game_id": "0022500001",
        "canonical_game_id": "0022500001",
        "source_row_sha256": "a" * 64,
        "game_date": date(2026, 4, 12),
        "season": "2025-26",
        "season_type": "Regular Season",
        "home_team_id": 1,
        "away_team_id": 2,
        "sportsbook_id": "book-a",
        "retrieved_at": datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
        "data_available_at": datetime(2026, 7, 24, 12, tzinfo=timezone.utc),
    }
    value.update(overrides)
    return value


def _selections():
    return [
        {
            "selection_key": "home",
            "selection_label": "Home",
            "price_american": -110,
            "pair_status": "not_applicable",
        },
        {
            "selection_key": "away",
            "selection_label": "Away",
            "price_american": 100,
            "pair_status": "not_applicable",
        },
    ]


def test_historical_static_requires_unknown_timing_and_preserves_selection_pair():
    normalized = validate_market_observation(_header(), _selections())

    assert normalized["timing_precision"] == "unknown"
    assert normalized["data_available_at"].tzinfo == timezone.utc


def test_forward_observation_requires_declared_time():
    with pytest.raises(MarketObservationContractError, match="timing precision"):
        validate_market_observation(
            _header(
                snapshot_type="forward",
                timing_precision="unknown",
                source_import_id=None,
            ),
            _selections(),
        )


def test_source_row_hash_must_be_lowercase_hex_sha256():
    with pytest.raises(MarketObservationContractError, match="SHA-256"):
        validate_market_observation(_header(source_row_sha256="g" * 64), _selections())


def test_selection_specific_total_pair_is_allowed():
    normalized = validate_market_observation(
        _header(market_type="total"),
        [
            {
                "selection_key": "over",
                "selection_label": "Over",
                "line_value": 224.5,
                "price_american": -110,
                "pair_status": "selection_specific",
            },
            {
                "selection_key": "under",
                "selection_label": "Under",
                "line_value": 225.0,
                "price_american": -105,
                "pair_status": "selection_specific",
            },
        ],
    )

    assert normalized["market_type"] == "total"
