"""Focused tests for the daily canonical player-fact selector."""

from datetime import date
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.player_game_fact_daily_service import (
    _current_family_projection_evidence,
    _fact_identity_set_sha256,
    build_daily_player_fact_replay_manifest,
    collect_daily_player_game_facts,
    _publish_and_reconcile,
    select_pending_completed_game_ids,
    select_daily_player_fact_scope,
    validate_daily_player_fact_replay_manifest,
)
from app.services.ingestion_run_service import _mark_daily_replay_manifest_failed
from app.services.player_game_fact_replay_service import source_row_set_sha256
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


def _source_fact(game_id: str, row_hash: str = "d" * 64):
    return {
        "canonical_game_id": game_id,
        "canonical_player_id": 1,
        "canonical_team_id": 2,
        "source_name": "fixture_source",
        "source_row_key": f"{game_id}:1:2",
        "parser_version": "fixture-v1",
        "source_row_sha256": row_hash,
    }


def test_current_projection_evidence_preserves_response_rows_and_identity():
    fact = SimpleNamespace(revision_id="revision-1")
    revision = SimpleNamespace(
        canonical_game_id="g1",
        canonical_player_id=1,
        canonical_team_id=2,
        source_name="fixture_source",
        source_row_key="g1:1:2",
        parser_version="fixture-v1",
        source_row_sha256="d" * 64,
        source_response_sha256="a" * 64,
        raw_payload={"response_sha256": "b" * 64},
    )

    class Query:
        def filter(self, *_args):
            return self

        def all(self):
            return [fact]

    db = SimpleNamespace(
        query=lambda _model: Query(),
        get=lambda _model, revision_id: revision if revision_id == "revision-1" else None,
    )

    evidence = _current_family_projection_evidence(db, "g1", "traditional")

    assert evidence is not None
    assert evidence["response_sha256"] == "a" * 64
    assert evidence["source_row_set_sha256"] == source_row_set_sha256(
        [_source_fact("g1")], "g1"
    )
    assert evidence["source_identity_set_sha256"] == _fact_identity_set_sha256(
        [_source_fact("g1")], "g1"
    )


def test_current_projection_allows_mixed_historical_response_hashes():
    facts = [
        SimpleNamespace(revision_id="revision-1"),
        SimpleNamespace(revision_id="revision-2"),
    ]
    revisions = {
        "revision-1": SimpleNamespace(
            canonical_game_id="g1",
            canonical_player_id=1,
            canonical_team_id=2,
            source_name="fixture_source",
            source_row_key="g1:1:2",
            parser_version="fixture-v1",
            source_row_sha256="d" * 64,
            source_response_sha256="a" * 64,
            raw_payload={},
        ),
        "revision-2": SimpleNamespace(
            canonical_game_id="g1",
            canonical_player_id=3,
            canonical_team_id=4,
            source_name="fixture_source",
            source_row_key="g1:3:4",
            parser_version="fixture-v1",
            source_row_sha256="e" * 64,
            source_response_sha256="b" * 64,
            raw_payload={},
        ),
    }

    class Query:
        def filter(self, *_args):
            return self

        def all(self):
            return facts

    db = SimpleNamespace(
        query=lambda _model: Query(),
        get=lambda _model, revision_id: revisions[revision_id],
    )

    evidence = _current_family_projection_evidence(db, "g1", "traditional")

    assert evidence is not None
    assert evidence["response_sha256"] is None
    assert len(evidence["source_row_set_sha256"]) == 64


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


def test_daily_task_replay_uses_published_hash_after_reviewed_response_drift():
    batch = _manifest_batch(1, "g1")
    batch["advanced"] = [dict(batch["advanced"][0])]
    batch["traditional"][0].update({
        "response_sha256": "c" * 64,
        "published_response_sha256": "a" * 64,
        "source_row_set_sha256": "d" * 64,
        "response_hash_changed": True,
    })
    batch["advanced"][0].update({
        "response_sha256": "b" * 64,
        "published_response_sha256": "b" * 64,
        "source_row_set_sha256": "e" * 64,
        "response_hash_changed": False,
    })
    manifest = build_daily_player_fact_replay_manifest(
        run_id="run-1", task_run_id="task-1", season="2026-27",
        season_type="Regular Season", batches=[batch], status="completed",
    )
    task = SimpleNamespace(
        task_run_id="task-1", run_id="run-1", details={"replay_manifest": manifest}
    )
    args = SimpleNamespace(
        replay_task_id="task-1", batch_number=1, max_games=1, replay_run_id=None,
        season="2025-26", season_type="Regular Season", batch=None,
    )
    ids, number = _load_game_ids(SimpleNamespace(get=lambda _model, _id: task), args)
    assert ids == ["g1"] and number == 1
    assert not hasattr(args, "expected_response_hashes")
    assert args.expected_source_row_set_hashes["traditional"]["g1"] == "d" * 64


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
            "traditional_facts": [_source_fact(game_id)],
            "advanced_facts": [_source_fact(game_id)],
            "traditional_games": evidence, "advanced_games": evidence,
        }

    def publish(collected, **kwargs):
        for family in ("traditional", "advanced"):
            for row in collected[f"{family}_games"]:
                row["published_source_row_set_sha256"] = row["source_row_set_sha256"]
                row["published_response_sha256"] = row["response_sha256"]
                row["response_hash_changed"] = False
        task.details = dict(kwargs["task_details"])
        return {"reconciliation": {"status": "passed"}}

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
        "app.services.player_game_fact_daily_service._current_family_projection_evidence",
        return_value=None,
    ), patch(
        "app.services.player_game_fact_daily_service._publish_and_reconcile",
        side_effect=publish,
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

    evidence = [
        {
            "game_id": game_id,
            "response_sha256": hash_value * 64,
            "retrieved_at": datetime(2026, 10, 21, 12, tzinfo=timezone.utc).isoformat(),
        }
        for game_id, hash_value in (("g1", "a"), ("g2", "b"))
    ]

    def fail_after_traditional(_specs, *, progress_callback, **_kwargs):
        progress_callback("traditional", [evidence[0]])
        progress_callback("traditional", [evidence[1]])
        raise RuntimeError("Advanced provider timeout")

    with patch(
        "app.services.player_game_fact_daily_service.get_db_context", side_effect=lambda: Context()
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {"eligible_completed_games": 1},
            "pending_game_ids": ["g1", "g2"],
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
                max_games_per_batch=2,
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


def test_exact_daily_scope_selects_only_the_requested_pending_game():
    assert select_daily_player_fact_scope(
        ["g1", "g2", "g3"], game_id="g2"
    ) == ["g2"]
    assert select_daily_player_fact_scope(["g1", "g2"]) == ["g1", "g2"]


def test_exact_daily_scope_rejects_a_game_outside_the_pending_inventory():
    with pytest.raises(ValueError, match="not in the completed daily inventory"):
        select_daily_player_fact_scope(["g1", "g2"], game_id="g3")


def test_exact_daily_scope_allows_a_fully_covered_game_for_guarded_recapture():
    assert select_daily_player_fact_scope(
        ["g1"], game_id="g2", covered_game_ids=["g2"]
    ) == ["g2"]


def test_daily_collector_passes_only_the_explicit_game_to_collection():
    class DB:
        pass

    class Context:
        def __enter__(self):
            return DB()

        def __exit__(self, *_args):
            return False

    evidence = [{
        "game_id": "g2",
        "response_sha256": "b" * 64,
        "retrieved_at": datetime(2026, 10, 21, 12, tzinfo=timezone.utc).isoformat(),
    }]
    captured = {}

    def collect(specs, *, progress_callback, **_kwargs):
        captured["game_ids"] = [spec.game_id for spec in specs]
        progress_callback("traditional", evidence)
        progress_callback("advanced", evidence)
        return {
            "traditional_facts": [_source_fact("g2")],
            "advanced_facts": [_source_fact("g2")],
            "traditional_games": evidence, "advanced_games": evidence,
        }

    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        side_effect=lambda: Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {"eligible_completed_games": 3},
            "pending_game_ids": ["g1", "g2", "g3"],
            "blocked_game_ids": [],
        },
    ), patch(
        "app.services.player_game_fact_daily_service.resolve_completed_game_specs",
        side_effect=lambda _db, game_ids, **_kwargs: [
            SimpleNamespace(game_id=game_id, game_date=date(2026, 10, 21))
            for game_id in game_ids
        ],
    ), patch(
        "app.services.player_game_fact_daily_service.collect_player_game_batch",
        side_effect=collect,
    ), patch(
        "app.services.player_game_fact_daily_service._current_family_projection_evidence",
        return_value=None,
    ), patch(
        "app.services.player_game_fact_daily_service._publish_and_reconcile",
        return_value={"reconciliation": {"status": "passed"}},
    ):
        result = collect_daily_player_game_facts(
            season="2026-27", run_id="run-1", game_id="g2"
        )

    assert captured["game_ids"] == ["g2"]
    assert result["replay_manifest"]["batches"][0]["game_ids"] == ["g2"]


def test_covered_game_recapture_stops_before_publication_on_changed_source_row():
    class DB:
        pass

    class Context:
        def __enter__(self):
            return DB()

        def __exit__(self, *_args):
            return False

    persisted = []
    expected = {
        "traditional": {"g1": "a" * 64},
        "advanced": {"g1": "b" * 64},
    }
    actual = {
        "traditional": [{"game_id": "g1", "response_sha256": "c" * 64,
                         "retrieved_at": datetime(2026, 10, 22, 12, tzinfo=timezone.utc).isoformat()}],
        "advanced": [{"game_id": "g1", "response_sha256": "b" * 64,
                      "retrieved_at": datetime(2026, 10, 22, 12, tzinfo=timezone.utc).isoformat()}],
    }

    def collect(specs, *, progress_callback, **_kwargs):
        for family in ("traditional", "advanced"):
            progress_callback(family, actual[family])
        return {
            "traditional_facts": [{**_source_fact("g1", "e" * 64), "source_row_key": "replacement-identity"}],
            "advanced_facts": [_source_fact("g1")],
            "traditional_games": actual["traditional"],
            "advanced_games": actual["advanced"],
        }

    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        side_effect=lambda: Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {
                "eligible_completed_games": 1,
                "games": [{"game_id": "g1", "state": "covered"}],
            },
            "pending_game_ids": [],
            "blocked_game_ids": [],
        },
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "passed", "blocking": {}},
    ), patch(
        "app.services.player_game_fact_daily_service._current_game_response_hashes",
        return_value=expected,
    ), patch(
        "app.services.player_game_fact_daily_service._current_game_source_row_set_hashes",
        return_value={
            family: {"g1": source_row_set_sha256([_source_fact("g1")], "g1")}
            for family in ("traditional", "advanced")
        },
    ), patch(
        "app.services.player_game_fact_daily_service._persist_task_details",
        side_effect=lambda _task_id, details: persisted.append(dict(details)),
    ), patch(
        "app.services.player_game_fact_daily_service.resolve_completed_game_specs",
        return_value=[SimpleNamespace(game_id="g1", game_date=date(2026, 10, 20))],
    ), patch(
        "app.services.player_game_fact_daily_service.collect_player_game_batch",
        side_effect=collect,
    ), patch(
        "app.services.player_game_fact_daily_service._current_family_projection_evidence",
        side_effect=lambda _db, _game, family: {
            "response_sha256": expected[family]["g1"],
            "source_row_set_sha256": source_row_set_sha256([_source_fact("g1")], "g1"),
            "source_identity_set_sha256": "baseline-identity",
        },
    ), patch(
        "app.services.player_game_fact_daily_service._fact_identity_set_sha256",
        return_value="replacement-identity",
    ), patch(
        "app.services.player_game_fact_daily_service._publish_and_reconcile",
    ) as publish:
        with pytest.raises(ValueError, match="traditional source identity/row set changed"):
            collect_daily_player_game_facts(
                season="2026-27", run_id="run-1", task_run_id="task-1", game_id="g1"
            )

    manifest = persisted[-1]["replay_manifest"]
    assert manifest["status"] == "failed"
    assert manifest["batches"][0]["game_ids"] == ["g1"]
    assert manifest["batches"][0]["traditional"][0]["response_sha256"] == "c" * 64
    assert len(manifest["batches"][0]["advanced"]) == 1
    assert manifest["batches"][0]["baseline_response_hashes"] == expected
    publish.assert_not_called()


def test_covered_game_recapture_records_response_drift_with_identical_rows():
    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    old_hashes = {
        "traditional": {"g1": "a" * 64},
        "advanced": {"g1": "b" * 64},
    }
    row_set = source_row_set_sha256([_source_fact("g1")], "g1")
    current_rows = {
        "traditional": {"g1": row_set},
        "advanced": {"g1": row_set},
    }
    retrieved_at = datetime(2026, 10, 22, 12, tzinfo=timezone.utc).isoformat()

    def collect(_specs, *, progress_callback, **_kwargs):
        traditional = [{"game_id": "g1", "response_sha256": "c" * 64,
                        "retrieved_at": retrieved_at}]
        advanced = [{"game_id": "g1", "response_sha256": "b" * 64,
                     "retrieved_at": retrieved_at}]
        progress_callback("traditional", traditional)
        progress_callback("advanced", advanced)
        return {
            "traditional_facts": [_source_fact("g1")],
            "advanced_facts": [_source_fact("g1")],
            "traditional_games": traditional,
            "advanced_games": advanced,
        }

    def publish(collected, **_kwargs):
        for family in ("traditional", "advanced"):
            for row in collected[f"{family}_games"]:
                row["published_source_row_set_sha256"] = row["source_row_set_sha256"]
                row["published_response_sha256"] = old_hashes[family]["g1"]
                row["response_hash_changed"] = (
                    row["response_sha256"] != old_hashes[family]["g1"]
                )
        return {"reconciliation": {"status": "passed"}}

    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        side_effect=lambda: Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {"eligible_completed_games": 1,
                       "games": [{"game_id": "g1", "state": "covered"}]},
            "pending_game_ids": [], "blocked_game_ids": [],
        },
    ), patch(
        "app.services.player_game_fact_daily_service.build_reconciliation_report",
        return_value={"status": "passed", "blocking": {}},
    ), patch(
        "app.services.player_game_fact_daily_service._current_game_response_hashes",
        return_value=old_hashes,
    ), patch(
        "app.services.player_game_fact_daily_service._current_game_source_row_set_hashes",
        return_value=current_rows,
    ), patch(
        "app.services.player_game_fact_daily_service.resolve_completed_game_specs",
        return_value=[SimpleNamespace(game_id="g1", game_date=date(2026, 10, 20))],
    ), patch(
        "app.services.player_game_fact_daily_service.collect_player_game_batch",
        side_effect=collect,
    ), patch(
        "app.services.player_game_fact_daily_service._current_family_projection_evidence",
        side_effect=lambda _db, _game, family: {
            "response_sha256": old_hashes[family]["g1"],
            "source_row_set_sha256": row_set,
            "source_identity_set_sha256": "same-identity",
        },
    ), patch(
        "app.services.player_game_fact_daily_service._fact_identity_set_sha256",
        return_value="same-identity",
    ), patch(
        "app.services.player_game_fact_daily_service._publish_and_reconcile",
        side_effect=publish,
    ):
        result = collect_daily_player_game_facts(
            season="2026-27", run_id="run-1", game_id="g1"
        )

    batch = result["replay_manifest"]["batches"][0]
    assert batch["traditional"][0]["response_hash_changed"] is True
    assert batch["traditional"][0]["published_response_sha256"] == "a" * 64
    assert batch["traditional"][0]["source_row_set_sha256"] == row_set
    assert batch["traditional"][0]["published_source_row_set_sha256"] == row_set
    assert batch["advanced"][0]["response_hash_changed"] is False


def test_daily_spec_resolution_failure_preserves_failed_manifest():
    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return False

    persisted = []
    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        side_effect=lambda: Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._inventory",
        return_value={
            "report": {"eligible_completed_games": 1, "games": []},
            "pending_game_ids": ["g1"],
            "blocked_game_ids": [],
        },
    ), patch(
        "app.services.player_game_fact_daily_service._persist_task_details",
        side_effect=lambda _task_id, details: persisted.append(dict(details)),
    ), patch(
        "app.services.player_game_fact_daily_service.resolve_completed_game_specs",
        side_effect=ValueError("schedule identity changed"),
    ), patch(
        "app.services.player_game_fact_daily_service.collect_player_game_batch"
    ) as collect:
        with pytest.raises(ValueError, match="schedule identity changed"):
            collect_daily_player_game_facts(
                season="2026-27", run_id="run-1", task_run_id="task-1", game_id="g1"
            )

    manifest = persisted[-1]["replay_manifest"]
    assert manifest["status"] == "failed"
    assert manifest["batches"][0]["status"] == "failed"
    assert manifest["batches"][0]["game_ids"] == ["g1"]
    collect.assert_not_called()


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


def test_daily_batch_verifies_and_records_post_publication_row_set():
    class Context:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    row_set = "d" * 64
    collected = {
        "traditional_facts": [],
        "advanced_facts": [],
        "traditional_games": [{
            "game_id": "g1", "response_sha256": "a" * 64,
            "source_row_set_sha256": row_set,
        }],
        "advanced_games": [{
            "game_id": "g1", "response_sha256": "b" * 64,
            "source_row_set_sha256": row_set,
        }],
    }
    with patch(
        "app.services.player_game_fact_daily_service.get_db_context",
        return_value=Context(),
    ), patch(
        "app.services.player_game_fact_daily_service._resolve_missing_players",
        return_value={"requested": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_player_game_facts",
        return_value={"created": 0},
    ), patch(
        "app.services.player_game_fact_daily_service.publish_advanced_facts",
        return_value={"created": 0},
    ), patch(
        "app.services.player_game_fact_daily_service._current_family_projection_evidence",
        side_effect=lambda _db, _game_id, family: {
            "response_sha256": None if family == "traditional" else "b" * 64,
            "source_row_set_sha256": row_set,
            "source_identity_set_sha256": "identity",
        },
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
        _publish_and_reconcile(
            collected, season="2026-27", game_ids=["g1"], max_games=1
        )

    assert collected["traditional_games"][0]["published_source_row_set_sha256"] == row_set
    assert collected["traditional_games"][0]["published_response_sha256"] is None
    assert collected["traditional_games"][0]["response_hash_changed"] is True
    assert collected["advanced_games"][0]["response_hash_changed"] is False
