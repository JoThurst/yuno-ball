"""Read-only audit helpers for the Program G baseline-model input gate."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Iterable, Mapping


MODEL_FEATURES = {
    "strength": ("net_rtg_season", "season_games_used"),
    "form": ("net_rtg_lastn", "window_games_used"),
    "schedule": (
        "days_rest",
        "is_b2b",
        "is_3_in_4",
        "is_4_in_5",
        "is_5_in_7",
    ),
    "matchup_context": (
        "pace_season",
        "pace_lastn",
        "efg_season",
        "efg_lastn",
        "tov_pct_season",
        "tov_pct_lastn",
        "orb_pct_season",
        "orb_pct_lastn",
        "ftr_season",
        "ftr_lastn",
        "pct_pts_3pt_season",
        "pct_pts_3pt_lastn",
    ),
}

FORBIDDEN_TARGET_FIELDS = frozenset(
    {"result", "wl", "pts", "point_diff", "home_score", "away_score"}
)

REQUIRED_MODEL_FIELDS = tuple(
    field for fields in MODEL_FEATURES.values() for field in fields
)


def _value(row: Any, field: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(field, default)
    return getattr(row, field, default)


def _as_feature_row(row: Any) -> dict[str, Any]:
    fields = {
        "game_id",
        "team_id",
        "game_date",
        "scheduled_tipoff",
        "feature_as_of",
        "data_available_at",
        "source_latest_game_date",
        "calculation_version",
        *[field for fields in MODEL_FEATURES.values() for field in fields],
    }
    if isinstance(row, Mapping):
        return {field: row.get(field) for field in fields} | {
            key: value for key, value in row.items() if key in FORBIDDEN_TARGET_FIELDS
        }
    return {field: getattr(row, field, None) for field in fields} | {
        field: getattr(row, field, None) for field in FORBIDDEN_TARGET_FIELDS
    }


def _timestamp_order(value: Any) -> tuple[int, str]:
    """Prefer valid timestamps over nulls with deterministic tie ordering."""
    if value is None:
        return (0, "")
    if isinstance(value, datetime):
        return (1, value.isoformat())
    return (1, str(value))


def select_latest_model_rows(
    rows: Iterable[Any], key_fields: tuple[str, ...]
) -> dict[tuple[Any, ...], Any]:
    """Select the latest revision, preferring non-null feature timestamps."""
    selected: dict[tuple[Any, ...], Any] = {}
    for raw_row in rows:
        key = tuple(_value(raw_row, field) for field in key_fields)
        current = selected.get(key)
        if current is None or _timestamp_order(_value(raw_row, "feature_as_of")) > _timestamp_order(_value(current, "feature_as_of")):
            selected[key] = raw_row
    return selected


def audit_model_inputs(
    *,
    season: str,
    season_type: str,
    team_rows: Iterable[Any],
    environment_rows: Iterable[Any],
    outcome_rows: Iterable[Any],
) -> dict[str, Any]:
    """Audit paired pregame inputs without writing or mutating any source rows."""
    latest_team_objects = select_latest_model_rows(team_rows, ("game_id", "team_id"))
    latest_environment_objects = select_latest_model_rows(environment_rows, ("game_id",))
    latest_team_rows = {
        key: _as_feature_row(row) for key, row in latest_team_objects.items()
    }
    latest_environment_rows = {
        key: _as_feature_row(row) for key, row in latest_environment_objects.items()
    }

    teams_by_game: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in latest_team_rows.values():
        teams_by_game[str(row.get("game_id"))].append(row)
    environment_game_ids = {
        str(key[0]) for key in latest_environment_rows
    }

    eligible_game_ids = sorted(
        game_id
        for game_id, rows in teams_by_game.items()
        if len(rows) == 2 and game_id in environment_game_ids
    )
    eligible_rows = [
        row for game_id in eligible_game_ids for row in teams_by_game[game_id]
    ]

    outcomes = {
        (str(_value(row, "game_id")), _value(row, "team_id")): row
        for row in outcome_rows
    }
    outcome_games = {
        game_id
        for game_id in eligible_game_ids
        if all((game_id, row.get("team_id")) in outcomes for row in teams_by_game[game_id])
    }

    violations = {
        "missing_pregame_timestamps": 0,
        "feature_after_tipoff": 0,
        "data_available_after_feature": 0,
        "source_latest_game_not_prior": 0,
        "forbidden_target_fields": 0,
    }
    for row in eligible_rows:
        feature_as_of = row.get("feature_as_of")
        scheduled_tipoff = row.get("scheduled_tipoff")
        if not isinstance(feature_as_of, datetime) or not isinstance(
            scheduled_tipoff, datetime
        ):
            violations["missing_pregame_timestamps"] += 1
        elif feature_as_of >= scheduled_tipoff:
            violations["feature_after_tipoff"] += 1
        data_available_at = row.get("data_available_at")
        if (
            isinstance(data_available_at, datetime)
            and isinstance(feature_as_of, datetime)
            and data_available_at > feature_as_of
        ):
            violations["data_available_after_feature"] += 1
        source_latest_game_date = row.get("source_latest_game_date")
        game_date = row.get("game_date")
        if (
            isinstance(source_latest_game_date, date)
            and isinstance(game_date, date)
            and source_latest_game_date >= game_date
        ):
            violations["source_latest_game_not_prior"] += 1
        if any(row.get(field) is not None for field in FORBIDDEN_TARGET_FIELDS):
            violations["forbidden_target_fields"] += 1

    feature_coverage = {}
    for family, fields in MODEL_FEATURES.items():
        family_fields = {}
        for field in fields:
            available = sum(row.get(field) is not None for row in eligible_rows)
            family_fields[field] = {
                "available_rows": available,
                "missing_rows": len(eligible_rows) - available,
            }
        feature_coverage[family] = family_fields

    required_feature_missing = {
        field: sum(row.get(field) is None for row in eligible_rows)
        for field in REQUIRED_MODEL_FIELDS
    }
    required_feature_missing_rows = sum(required_feature_missing.values())
    integrity_failures = sum(violations.values())
    if not eligible_game_ids:
        status = "blocked_no_completed_game_evidence"
    elif integrity_failures:
        status = "blocked_integrity"
    elif required_feature_missing_rows:
        status = "blocked_missing_required_features"
    elif outcome_games != set(eligible_game_ids):
        status = "blocked_outcome_coverage"
    else:
        status = "ready_for_baseline_experiment"

    return {
        "season": season,
        "season_type": season_type,
        "status": status,
        "selected_team_rows": len(latest_team_rows),
        "selected_environment_games": len(latest_environment_rows),
        "eligible_games": len(eligible_game_ids),
        "eligible_team_rows": len(eligible_rows),
        "games_with_outcomes": len(outcome_games),
        "feature_coverage": feature_coverage,
        "required_feature_missing": required_feature_missing,
        "required_feature_missing_rows": required_feature_missing_rows,
        "violations": violations,
        "writes_performed": False,
    }
