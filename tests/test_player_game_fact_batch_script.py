"""Atomic publication contract for the bounded C7 command."""

from unittest.mock import patch

import pytest

from scripts.collect_player_game_fact_batch import _publish_and_reconcile


def test_c7_publication_reconciles_on_the_same_session_before_commit():
    db = object()
    with patch(
        "scripts.collect_player_game_fact_batch.publish_player_game_facts",
        return_value={"facts_updated": 1},
    ) as traditional, patch(
        "scripts.collect_player_game_fact_batch.publish_advanced_facts",
        return_value={"facts_updated": 1},
    ) as advanced, patch(
        "scripts.collect_player_game_fact_batch.build_reconciliation_report",
        return_value={"status": "failed", "reason": "team total mismatch"},
    ) as reconcile:
        with pytest.raises(ValueError, match="C5 reconciliation failed for batch"):
            _publish_and_reconcile(
                db,
                traditional_facts=[{"family": "traditional"}],
                advanced_facts=[{"family": "advanced"}],
                season="2026-27",
                game_ids=["g1"],
                max_games=1,
            )

    traditional.assert_called_once_with([{"family": "traditional"}], db=db)
    advanced.assert_called_once_with([{"family": "advanced"}], db=db)
    reconcile.assert_called_once_with(
        db, season="2026-27", game_ids=["g1"], max_games=1
    )
