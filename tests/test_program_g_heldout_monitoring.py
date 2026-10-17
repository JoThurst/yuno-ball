from scripts.program_g_heldout_monitoring import summarize_heldout_incremental_lift


def _direction(loss, *, coverage=1.0, games=8):
    return {
        "status": "complete",
        "coverage_pass": coverage >= 0.95,
        "heldout_coverage": coverage,
        "heldout_games": games,
        "heldout_complete_games": int(games * coverage),
        "heldout": {"win": {"log_loss": loss}},
    }


def test_monitoring_holds_mixed_direction_lift():
    report = {"definitions": {
        "strength_form_control": {"directions": {
            "a_to_b": _direction(0.6), "b_to_a": _direction(0.61),
        }},
        "schedule": {"directions": {
            "a_to_b": _direction(0.59), "b_to_a": _direction(0.62),
        }},
    }}

    summary = summarize_heldout_incremental_lift(report)

    assert summary["status"] == "complete"
    assert summary["production_prediction_approved"] is False
    assert summary["candidates"]["schedule"] == {
        "status": "held_no_uniform_lift",
        "log_loss_delta_vs_control": {"a_to_b": -0.01, "b_to_a": 0.01},
    }


def test_monitoring_blocks_comparison_without_full_paired_coverage():
    report = {"definitions": {
        "strength_form_control": {"directions": {
            "a_to_b": _direction(0.6), "b_to_a": _direction(0.61),
        }},
        "schedule": {"directions": {
            "a_to_b": _direction(0.59, coverage=0.95),
            "b_to_a": _direction(0.60),
        }},
    }}

    summary = summarize_heldout_incremental_lift(report)

    assert summary["candidates"]["schedule"] == {
        "status": "blocked_unpaired_population",
        "log_loss_delta_vs_control": {},
    }


def test_monitoring_reports_improvement_without_approval():
    report = {"definitions": {
        "strength_form_control": {"directions": {
            "a_to_b": _direction(0.6), "b_to_a": _direction(0.61),
        }},
        "schedule": {"directions": {
            "a_to_b": _direction(0.59), "b_to_a": _direction(0.60),
        }},
    }}

    summary = summarize_heldout_incremental_lift(report)

    assert summary["candidates"]["schedule"]["status"] == "observed_both_direction_improvement"
    assert summary["production_prediction_approved"] is False
