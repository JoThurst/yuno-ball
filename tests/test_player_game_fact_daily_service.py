"""Focused tests for the daily canonical player-fact selector."""

from datetime import date
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.player_game_fact_daily_service import (
    build_daily_player_fact_replay_manifest,
    collect_daily_player_game_facts,
    _publish_and_reconcile,
    select_pending_completed_game_ids,
    validate_daily_player_fact_replay_manifest,
)
from app.services.ingestion_run_service import _mark_daily_replay_manifest_failed
from scripts.collect_player_game_fact_batch import _load_game_ids


def _manifest_batch(number: int, game_id: str, *, status: str = "completed"):
    timestamp = datetime(2026, 10, 21, 12, tzinfo=timezone.utc).isoformat()
    evidence = [{"game_id": game_id, "response_sha256": "a" * 64, "retrieved_at": timestamp}]
    return {
        "batch": number,
        "attempt_id": f"attempt-{number}",
        "status": status,
        "game_ids": [game_id],
        "traditional": evidence,
        "advanced": evidence,
    }


def _pair(game_id: str, *, result: str = "W"):
    game_date = date(2026, 4, 1)
    return [
        SimpleNamespace(
            game_id=game_id,
            game_date=game_date,
            team_id=1,
            opponent_team_id=2,
            result=result,
        ),
        SimpleNamespace(
            game_id=game_id,
            game_date=game_date,
            team_id=2,
            opponent_team_id=1,
            result="L" if result == "W" else result,
        ),
    ]


def test_daily_manifest_preserves_one_game_scope_and_hashes():
    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        task_run_id="task-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[
            {
                **_manifest_batch(1, "0022600001"),
            }
        ],
        status="completed",
    )

    assert validate_daily_player_fact_replay_manifest(manifest) == ["0022600001"]
    assert manifest["endpoints"] == {
        "traditional": "BoxScoreTraditionalV3",
        "advanced": "BoxScoreAdvancedV3",
    }


def test_daily_manifest_rejects_absent_or_overlapping_scope():
    with pytest.raises(ValueError, match="manifest version"):
        validate_daily_player_fact_replay_manifest({})

    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        task_run_id="task-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[
            _manifest_batch(1, "g1"),
            _manifest_batch(2, "g1"),
        ],
        status="partial",
    )
    with pytest.raises(ValueError, match="overlaps"):
        validate_daily_player_fact_replay_manifest(manifest)


def test_daily_manifest_requires_complete_identity_and_retrieval_evidence():
    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        task_run_id="task-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[_manifest_batch(1, "g1")],
        status="completed",
    )
    manifest["batches"][0]["advanced"][0]["retrieved_at"] = "2026-10-21T12:00:00"
    with pytest.raises(ValueError, match="naive"):
        validate_daily_player_fact_replay_manifest(manifest)


def test_daily_manifest_preserves_distinct_multibatch_replay_units():
    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        task_run_id="task-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[_manifest_batch(1, "g1"), _manifest_batch(2, "g2")],
        status="completed",
    )
    assert validate_daily_player_fact_replay_manifest(manifest) == ["g1", "g2"]
    assert [batch["game_ids"] for batch in manifest["batches"]] == [["g1"], ["g2"]]


def test_failed_task_retains_partial_provider_evidence_and_completed_batch():
    details = {
        "replay_manifest": {
            "status": "running",
            "batches": [
                _manifest_batch(1, "g1"),
                {
                    "batch": 2,
                    "attempt_id": "attempt-2",
                    "status": "collecting",
                    "game_ids": ["g2"],
                    "traditional": [{"game_id": "g2", "response_sha256": "b" * 64}],
                    "advanced": [],
                },
            ],
        }
    }
    failed = _mark_daily_replay_manifest_failed(details, "Advanced timeout")
    manifest = failed["replay_manifest"]
    assert manifest["status"] == "partial"
    assert manifest["batches"][0]["status"] == "completed"
    assert manifest["batches"][1]["status"] == "failed"
    assert manifest["batches"][1]["traditional"][0]["response_sha256"] == "b" * 64


def test_daily_task_replay_requires_exact_completed_batch():
    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1",
        task_run_id="task-1",
        season="2026-27",
        season_type="Regular Season",
        batches=[_manifest_batch(1, "g1"), _manifest_batch(2, "g2")],
        status="completed",
    )
    task = SimpleNamespace(
        task_run_id="task-1", run_id="run-1", details={"replay_manifest": manifest}
    )
    args = SimpleNamespace(
        replay_task_id="task-1", batch_number=2, max_games=25, replay_run_id=None,
        season="2025-26", season_type="Regular Season", batch=None,
    )
    ids, batch_number = _load_game_ids(SimpleNamespace(get=lambda _model, _id: task), args)
    assert ids == ["g2"]
    assert batch_number == 2
    assert args.season == "2026-27"

    task.details = {"replay_manifest": {}}
    with pytest.raises(ValueError, match="manifest version"):
        _load_game_ids(SimpleNamespace(get=lambda _model, _id: task), args)


def test_daily_collection_persists_distinct_completed_batches_with_task_identity():
    task = SimpleNamespace(status="running", details={})

    class DB:
        def get(self, _model, _key):
            return task

    class Context:
        def __enter__(self):
            return DB()

        def __exit__(self, *_args):
            return False

    collected_games = iter(["g1", "g2"])

    def collect(_specs, *, run_id, max_games, progress_callback):
        game_id = next(collected_games)
        evidence = [{
            "game_id": game_id,
            "response_sha256": "a" * 64,
            "retrieved_at": datetime(2026, 10, 21, 12, tzinfo=timezone.utc).isoformat(),
        }]
        progress_callback("traditional", evidence)
        progress_callback("advanced", evidence)
        return {
            "traditional_facts": [], "advanced_facts": [],
            "traditional_games": evidence, "advanced_games": evidence,
        }

    with patch(
        "app.services.player_game_fact_daily_service.get_db_context", side_effect=lambda: Context()
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {"eligible_completed_games": 2},
            "pending_game_ids": ["g1", "g2"],
            "blocked_game_ids": [],
        },
    ), patch(
        "app.services.player_game_fact_daily_service.resolve_completed_game_specs",
        return_value=[],
    ), patch(
        "app.services.player_game_fact_daily_service.collect_player_game_batch",
        side_effect=collect,
    ), patch(
        "app.services.player_game_fact_daily_service._resolve_missing_players",
        return_value={"requested": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_player_game_facts",
        return_value={"created": 0, "revisions_created": 0, "facts_updated": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_advanced_facts",
        return_value={"created": 0, "revisions_created": 0, "facts_updated": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "passed"},
    ), patch(
        "app.services.player_game_fact_daily_service.role_history_records_from_facts",
        return_value=[],
    ), patch(
        "app.services.player_game_fact_daily_service.publish_role_history",
        return_value=0,
    ):
        result = collect_daily_player_game_facts(
            season="2026-27", run_id="run-1", task_run_id="task-1",
            max_games_per_batch=1,
        )

    manifest = result["replay_manifest"]
    assert manifest["status"] == "completed"
    assert manifest["task_run_id"] == "task-1"
    assert [batch["game_ids"] for batch in manifest["batches"]] == [["g1"], ["g2"]]
    assert [batch["status"] for batch in manifest["batches"]] == ["completed", "completed"]
    assert [batch["traditional"][0]["response_sha256"] for batch in manifest["batches"]] == ["a" * 64] * 2
    assert task.details["replay_manifest"] == manifest


def test_daily_collection_persists_partial_provider_evidence_before_failure():
    task = SimpleNamespace(status="running", details={})

    class DB:
        def get(self, _model, _key):
            return task

    class Context:
        def __enter__(self):
            return DB()

        def __exit__(self, *_args):
            return False

    evidence = [{
        "game_id": "g1",
        "response_sha256": "a" * 64,
        "retrieved_at": datetime(2026, 10, 21, 12, tzinfo=timezone.utc).isoformat(),
    }]

    def fail_after_traditional(_specs, *, progress_callback, **_kwargs):
        progress_callback("traditional", evidence)
        raise RuntimeError("Advanced provider timeout")

    with patch(
        "app.services.player_game_fact_daily_service.get_db_context", side_effect=lambda: Context()
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {"eligible_completed_games": 1},
            "pending_game_ids": ["g1"],
            "blocked_game_ids": [],
        },
    ), patch(
        "app.services.player_game_fact_daily_service.resolve_completed_game_specs",
        return_value=[],
    ), patch(
        "app.services.player_game_fact_daily_service.collect_player_game_batch",
        side_effect=fail_after_traditional,
    ):
        with pytest.raises(RuntimeError, match="Advanced provider timeout"):
            collect_daily_player_game_facts(
                season="2026-27", run_id="run-1", task_run_id="task-1",
                max_games_per_batch=1,
            )

    manifest = task.details["replay_manifest"]
    assert manifest["status"] == "failed"
    assert manifest["batches"][0]["status"] == "failed"
    assert manifest["batches"][0]["traditional"] == evidence
    assert manifest["batches"][0]["advanced"] == []


def test_selector_returns_completed_game_missing_either_canonical_source():
    rows = _pair("game-1") + _pair("game-2") + _pair("game-3")

    pending = select_pending_completed_game_ids(
        rows,
        traditional_game_ids={"game-2"},
        advanced_game_ids={"game-3"},
    )

    assert pending == ["game-1", "game-2", "game-3"]


def test_selector_excludes_games_with_both_sources():
    assert select_pending_completed_game_ids(
        _pair("game-1"),
        traditional_game_ids={"game-1"},
        advanced_game_ids={"game-1"},
    ) == []


def test_selector_ignores_unfinished_nonreciprocal_and_incomplete_pairs():
    unfinished = _pair("game-1", result="")
    nonreciprocal = _pair("game-2")
    nonreciprocal[1].opponent_team_id = 99
    incomplete = _pair("game-3")[:1]

    assert select_pending_completed_game_ids(
        unfinished + nonreciprocal + incomplete,
        traditional_game_ids=set(),
        advanced_game_ids=set(),
    ) == []


def test_daily_batch_reconciliation_shares_transaction_and_rolls_back_on_failure():
    class Context:
        def __init__(self):
            self.db = object()
            self.entered = 0
            self.exit_args = None

        def __enter__(self):
            self.entered += 1
            return self.db

        def __exit__(self, *args):
            self.exit_args = args
            return False

    context = Context()
    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        return_value=context,
    ), patch(
        "app.services.player_game_fact_daily_service._resolve_missing_players",
        return_value={"requested": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_player_game_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_advanced_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "failed", "reason": "mismatch"},
    ) as reconcile:
        with pytest.raises(ValueError, match="C5 reconciliation failed"):
            _publish_and_reconcile(
                {"traditional_facts": [], "advanced_facts": [], "traditional_games": [], "advanced_games": []},
                season="2026-27",
                game_ids=["g1"],
                max_games=25,
            )

    assert context.entered == 1
    assert context.exit_args[0] is ValueError
    assert reconcile.call_args.args[0] is context.db


def test_daily_batch_publishes_role_history_only_after_reconciliation_passes():
    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    collected = {
        "traditional_facts": [{"canonical_game_id": "g1"}],
        "advanced_facts": [],
        "traditional_games": [],
        "advanced_games": [],
    }
    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        return_value=Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._resolve_missing_players",
        return_value={"requested": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_player_game_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_advanced_facts",
        return_value={"created": 1},
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "passed"},
    ), patch(
        "app.services.player_game_fact_daily_service.role_history_records_from_facts",
        return_value=[{"role_history_id": "history-1"}],
    ) as build_history, patch(
        "app.services.player_game_fact_daily_service.publish_role_history",
        return_value=1,
    ) as publish_history:
        result = _publish_and_reconcile(
            collected,
            season="2026-27",
            game_ids=["g1"],
            max_games=25,
        )

    build_history.assert_called_once_with(collected["traditional_facts"])
    publish_history.assert_called_once()
    assert result["role_history_rows"] == 1
