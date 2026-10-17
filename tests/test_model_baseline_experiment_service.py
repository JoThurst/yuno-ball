from datetime import datetime, timezone

import pytest

from app.services.model_baseline_experiment_service import (
    _calibration,
    _probability_report,
    compare_review_ready_feature_variants,
    review_feature_family_stability,
    run_calibrated_elo_baseline_experiment,
    run_elo_baseline_experiment,
    run_feature_family_ablation,
    run_schedule_component_sweep,
    run_schedule_definition_sweep,
    run_feature_family_season_heldout_sweep,
    run_naive_baseline_experiment,
    run_season_heldout_calibration_validation,
    run_season_heldout_window_sweep,
)


def test_calibration_reports_wilson_intervals_and_thin_bin_monitoring():
    report = _calibration([1, 0, 1, 0], [0.25, 0.25, 0.75, 0.75], bins=2)

    assert report["monitoring"] == {
        "method": "wilson_95_percent_interval",
        "minimum_bin_count": 25,
        "stable_bin_count": 0,
        "thin_bin_count": 2,
    }
    assert report["bins"][0]["meets_minimum_bin_count"] is False
    assert report["bins"][0]["observed_rate_interval_95"]["lower"] < 0.5
    assert report["bins"][0]["observed_rate_interval_95"]["upper"] > 0.5


def test_probability_report_includes_bands_with_complete_coverage():
    report = _probability_report(
        [0, 1, 1, 0, 1],
        [0.20, 0.40, 0.60, 0.80, 1.00],
    )

    bands = report["probability_bands"]
    assert bands["low_confidence"]["test_games"] == 1
    assert bands["competitive"]["test_games"] == 2
    assert bands["high_confidence"]["test_games"] == 2
    assert sum(band["coverage"] for band in bands.values()) == 1.0
    assert all("calibration" in band["win"] for band in bands.values())
    assert report["subgroup_acceptance"]["status"] == "blocked_thin_subgroup"


def _rows(count=8):
    return [
        {
            "game_id": str(index),
            "scheduled_tipoff": datetime(2025, 1, 1 + index, tzinfo=timezone.utc),
            "home_win": int(index % 2 == 0),
            "home_margin": float(index - 3),
            "game_total": float(200 + index),
        }
        for index in range(count)
    ]


def test_naive_baselines_use_only_prior_rows_and_report_blocks():
    report = run_naive_baseline_experiment(_rows(), min_train_games=3, blocks=2)

    assert report["status"] == "complete"
    assert report["blocks_evaluated"] == 2
    assert report["blocks"][0]["train_games"] == 3
    assert report["blocks"][1]["train_games"] > report["blocks"][0]["train_games"]
    assert report["aggregate"]["test_games"] == 5
    assert report["writes_performed"] is False


def test_baseline_experiment_blocks_when_warmup_exceeds_history():
    report = run_naive_baseline_experiment(_rows(3), min_train_games=3)

    assert report == {
        "status": "blocked_insufficient_history",
        "games": 3,
        "min_train_games": 3,
        "blocks_requested": 3,
        "blocks_evaluated": 0,
        "writes_performed": False,
    }


def test_elo_baseline_updates_after_prediction_and_reports_chronological_blocks():
    rows = _rows(8)
    for index, row in enumerate(rows):
        row["home_team_id"] = 1 if index % 2 == 0 else 2
        row["away_team_id"] = 2 if index % 2 == 0 else 1

    report = run_elo_baseline_experiment(rows, min_train_games=3, blocks=2)

    assert report["status"] == "complete"
    assert report["aggregate"]["test_games"] == 5
    assert report["blocks"][0]["train_games"] == 3
    assert report["writes_performed"] is False


def test_elo_baseline_blocks_without_team_identity():
    report = run_elo_baseline_experiment(_rows(8), min_train_games=3)

    assert report["status"] == "blocked_missing_team_ids"
    assert report["writes_performed"] is False


def test_calibrated_elo_fits_only_before_each_test_block():
    rows = _rows(8)
    for index, row in enumerate(rows):
        row["home_team_id"] = 1 if index % 2 == 0 else 2
        row["away_team_id"] = 2 if index % 2 == 0 else 1

    report = run_calibrated_elo_baseline_experiment(rows, min_train_games=3, blocks=2)

    assert report["status"] == "complete"
    assert report["aggregate"]["test_games"] == 5
    assert "ece" in report["aggregate"]["calibrated"]["calibration"]
    assert report["blocks"][0]["train_games"] == 3
    assert report["blocks"][1]["train_games"] > report["blocks"][0]["train_games"]
    assert report["writes_performed"] is False


def test_feature_ablation_is_chronological_and_withholds_missing_inputs():
    rows = _rows(8)
    for index, row in enumerate(rows):
        row["family_scores"] = {
            "strength": float(index % 3),
            "form": float(index % 2),
            "schedule": float(index - 3),
            "matchup_context": float(index) / 10,
        }
    rows[-1]["family_scores"]["form"] = None

    report = run_feature_family_ablation(rows, min_train_games=3, blocks=2)

    assert report["status"] == "complete"
    assert report["variants"]["strength"]["aggregate"]["test_games"] == 5
    assert report["variants"]["strength_form"]["withheld_test_games"] == 1
    assert report["variants"]["strength_form"]["blocks"][0]["train_games"] == 3
    assert report["writes_performed"] is False


def test_feature_ablation_reports_coverage_and_subgroup_review_thresholds():
    rows = _rows(20)
    for index, row in enumerate(rows):
        row["family_scores"] = {
            "strength": float(index),
            "form": float(index % 2),
            "schedule": float(index % 3),
            "matchup_context": float(index % 4),
        }

    report = run_feature_family_ablation(
        rows,
        min_train_games=5,
        blocks=2,
        minimum_test_coverage=0.90,
        minimum_subgroup_games=2,
    )

    strength = report["variants"]["strength"]
    assert strength["availability"] == {
        "effective_test_games": 15,
        "scored_test_games": 15,
        "coverage": 1.0,
        "minimum_coverage": 0.90,
        "meets_minimum_coverage": True,
    }
    assert strength["subgroup_acceptance"]["minimum_games"] == 2
    assert strength["subgroup_acceptance"]["status"] in {
        "review_ready",
        "blocked_thin_subgroup",
    }


def test_review_ready_feature_comparison_requires_gates_in_every_season():
    def variant(ready, log_loss):
        return {
            "families": ["strength"],
            "availability": {"coverage": 1.0},
            "subgroup_acceptance": {"all_bands_meet_minimum": ready},
            "aggregate": {"test_games": 10, "win": {"log_loss": log_loss, "brier": 0.2}},
        }

    report = compare_review_ready_feature_variants({
        "2024-25": {"variants": {"candidate": variant(True, 0.60), "thin": variant(False, 0.55)}},
        "2025-26": {"variants": {"candidate": variant(True, 0.62), "thin": variant(True, 0.58)}},
    })

    assert report["status"] == "complete"
    assert report["candidate_variants"] == ["candidate"]
    assert report["variants"]["candidate"]["stability"]["log_loss_range"] == pytest.approx(0.02)
    assert report["variants"]["thin"]["eligible_everywhere"] is False
    assert report["writes_performed"] is False


def test_feature_stability_review_reports_segments_and_sign_consistency():
    def variant(coefficients):
        return {
            "blocks": [
                {
                    "block": index + 1,
                    "test_start": f"2025-01-{index + 1}",
                    "test_end": f"2025-01-{index + 2}",
                    "test_games": 10,
                    "scored_test_games": 10,
                    "coverage": 1.0,
                    "status": "complete",
                    "standardized_coefficients": {
                        "strength": coefficient,
                        "form": 0.2,
                    },
                    "win": {"log_loss": 0.60 + index / 100, "brier": 0.20},
                }
                for index, coefficient in enumerate(coefficients)
            ]
        }

    report = review_feature_family_stability(
        {
            "2024-25": {"variants": {"candidate": variant([0.4, 0.2, 0.3])}},
            "2025-26": {"variants": {"candidate": variant([0.3, 0.1, 0.2])}},
        },
        ["candidate"],
    )

    candidate = report["variants"]["candidate"]
    assert report["status"] == "complete"
    assert candidate["eligible_everywhere"] is True
    assert candidate["feature_signs_consistent"] is True
    assert candidate["next_gate_ready"] is True
    assert candidate["seasons"]["2024-25"]["segments"][0]["log_loss"] == 0.60
    assert candidate["cross_season_feature_stability"]["strength"]["sign_consistent"] is True
    assert candidate["cross_season_feature_stability"]["strength"]["block_count"] == 6
    assert report["writes_performed"] is False


def test_feature_stability_review_blocks_a_thin_segment():
    report = review_feature_family_stability(
        {
            "2024-25": {
                "variants": {
                    "candidate": {
                        "blocks": [{
                            "block": 1,
                            "test_games": 10,
                            "scored_test_games": 9,
                            "coverage": 0.9,
                            "status": "complete",
                            "standardized_coefficients": {"strength": 0.4},
                            "win": {"log_loss": 0.7, "brier": 0.3},
                        }]
                    }
                }
            }
        },
        ["candidate"],
    )

    assert report["status"] == "complete"
    assert report["variants"]["candidate"]["eligible_everywhere"] is False


def test_schedule_definition_sweep_applies_home_perspective_transforms():
    rows = _rows(20)
    for index, row in enumerate(rows):
        row["family_scores"] = {
            "strength": float(index),
            "form": float(index % 2),
            "schedule": float(index - 10),
            "matchup_context": float(index % 4),
        }

    report = run_schedule_definition_sweep(
        {"2024-25": rows, "2025-26": rows},
        definitions=("rest_edge_clipped_1",),
        min_train_games=5,
        blocks=2,
    )

    assert report["status"] == "complete"
    assert report["definitions"]["rest_edge_clipped_1"]["stability"]["status"] == "complete"
    assert report["writes_performed"] is False


def test_schedule_component_sweep_accepts_custom_component_variants():
    rows = _rows(20)
    for index, row in enumerate(rows):
        row["family_scores"] = {
            "strength": float(index),
            "form": float(index % 2),
            "b2b_edge": float(index % 2),
        }

    report = run_schedule_component_sweep(
        {"2024-25": rows, "2025-26": rows},
        definitions={"strength_form_b2b": ("strength", "form", "b2b_edge")},
        min_train_games=5,
        blocks=2,
    )

    stability = report["definitions"]["strength_form_b2b"]["stability"]
    assert report["status"] == "complete"
    assert stability["variants"]["strength_form_b2b"]["eligible_everywhere"] is True
    assert report["writes_performed"] is False


def test_feature_family_season_heldout_sweep_freezes_source_fit():
    source = _rows(20)
    heldout = _rows(8)
    for rows in (source, heldout):
        for index, row in enumerate(rows):
            row["family_scores"] = {
                "strength": float(index % 4),
                "form": float(index % 3),
                "b2b_edge": float(index % 2),
            }

    report = run_feature_family_season_heldout_sweep(
        {"2024-25": source, "2025-26": heldout},
        {"strength_form_b2b": ("strength", "form", "b2b_edge")},
        min_train_games=5,
    )

    directions = report["definitions"]["strength_form_b2b"]["directions"]
    assert report["status"] == "complete"
    assert set(directions) == {"2024-25_to_2025-26", "2025-26_to_2024-25"}
    assert directions["2024-25_to_2025-26"]["heldout"]["test_games"] == 8
    assert directions["2024-25_to_2025-26"]["writes_performed"] is False


def test_heldout_validation_uses_dedicated_calibration_window_and_freezes_it():
    source = _rows(20)
    heldout = _rows(8)
    for index, row in enumerate(source + heldout):
        row["home_team_id"] = 1 if index % 2 == 0 else 2
        row["away_team_id"] = 2 if index % 2 == 0 else 1

    report = run_season_heldout_calibration_validation(
        source,
        heldout,
        train_fraction=0.50,
        calibration_fraction=0.25,
        min_train_games=5,
        min_calibration_games=5,
    )

    assert report["status"] == "complete"
    assert report["split"] == {
        "train_games": 10,
        "calibration_games": 5,
        "source_test_games": 5,
        "heldout_test_games": 8,
        "train_fraction": 0.50,
        "calibration_fraction": 0.25,
        "source_test_fraction": 0.25,
    }
    assert report["calibration_fit"]["calibration_games"] == 5
    assert report["source_test"]["raw"]["test_games"] == 5
    assert report["season_heldout"]["calibrated"]["test_games"] == 8
    assert report["writes_performed"] is False


def test_heldout_validation_blocks_when_calibration_window_is_too_small():
    source = _rows(8)
    heldout = _rows(4)
    for row in source + heldout:
        row["home_team_id"] = 1
        row["away_team_id"] = 2

    report = run_season_heldout_calibration_validation(
        source,
        heldout,
        train_fraction=0.50,
        calibration_fraction=0.25,
        min_train_games=3,
        min_calibration_games=3,
    )

    assert report["status"] == "blocked_insufficient_split"
    assert report["split"]["calibration_games"] == 2
    assert report["writes_performed"] is False


def test_heldout_window_sweep_runs_each_explicit_window_without_writes():
    source = _rows(20)
    heldout = _rows(8)
    for index, row in enumerate(source + heldout):
        row["home_team_id"] = 1 if index % 2 == 0 else 2
        row["away_team_id"] = 2 if index % 2 == 0 else 1

    report = run_season_heldout_window_sweep(
        source,
        heldout,
        windows=(("small_window", 0.50, 0.25),),
        min_train_games=5,
        min_calibration_games=5,
    )

    assert report["status"] == "complete"
    assert report["writes_performed"] is False
    assert report["windows"][0]["name"] == "small_window"
    assert report["windows"][0]["report"]["split"]["source_test_games"] == 5
