"""Research-only comparison of frozen Program G held-out reports."""

from __future__ import annotations

from typing import Any, Mapping


def summarize_heldout_incremental_lift(
    report: Mapping[str, Any], *, control_name: str = "strength_form_control"
) -> dict[str, Any]:
    """Compare candidates with the control on complete, identical populations.

    The current sweep does not retain scored game IDs. Full held-out coverage
    is therefore required before a candidate/control delta can be interpreted
    as paired evidence. A favorable delta remains research evidence only.
    """
    definitions = report.get("definitions", {})
    control = definitions.get(control_name)
    if not control:
        return {"status": "blocked_missing_control", "candidates": {}}

    control_directions = control.get("directions", {})
    if len(control_directions) != 2:
        return {"status": "blocked_incomplete_control", "candidates": {}}

    summaries = {}
    for name, candidate in definitions.items():
        if name == control_name:
            continue
        directions = candidate.get("directions", {})
        comparable = set(directions) == set(control_directions)
        deltas = {}
        if comparable:
            for direction, candidate_result in directions.items():
                baseline_result = control_directions[direction]
                if not all(
                    result.get("status") == "complete"
                    and result.get("coverage_pass") is True
                    and result.get("heldout_coverage") == 1.0
                    and result.get("heldout_complete_games") == result.get("heldout_games")
                    for result in (baseline_result, candidate_result)
                ) or candidate_result["heldout_games"] != baseline_result["heldout_games"]:
                    comparable = False
                    break
                candidate_loss = candidate_result["heldout"]["win"]["log_loss"]
                control_loss = baseline_result["heldout"]["win"]["log_loss"]
                deltas[direction] = round(candidate_loss - control_loss, 6)
        summaries[name] = {
            "status": (
                "blocked_unpaired_population" if not comparable
                else "observed_both_direction_improvement"
                if all(delta < 0 for delta in deltas.values())
                else "held_no_uniform_lift"
            ),
            "log_loss_delta_vs_control": deltas if comparable else {},
        }
    return {
        "status": "complete" if summaries else "blocked_no_candidates",
        "control": control_name,
        "negative_delta_is_better": True,
        "production_prediction_approved": False,
        "candidates": summaries,
    }
