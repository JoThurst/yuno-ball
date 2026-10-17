"""Read-only Program C reconciliation and correction evidence."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy.orm import Session

from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameAdvancedFactRevisionORM,
    PlayerGameFactORM,
    PlayerGameFactRevisionORM,
)
from app.services.player_game_fact_collection_service import validate_game_bound


def canonical_key(row: Any) -> tuple[str, int, int]:
    return (
        str(getattr(row, "canonical_game_id", getattr(row, "game_id", ""))),
        int(getattr(row, "canonical_player_id", getattr(row, "player_id", 0))),
        int(getattr(row, "canonical_team_id", getattr(row, "team_id", 0))),
    )


def compare_overlap(
    traditional_rows: Sequence[Any],
    legacy_rows: Sequence[Any],
) -> dict[str, Any]:
    """Compare only overlapping played rows; missing DNP rows remain visible separately."""
    traditional = {canonical_key(row): row for row in traditional_rows}
    legacy = {canonical_key(row): row for row in legacy_rows}
    overlap = sorted(set(traditional) & set(legacy))
    field_map = {
        "points": "points",
        "assists": "assists",
        "rebounds_total": "rebounds",
        "steals": "steals",
        "blocks": "blocks",
        "turnovers": "turnovers",
        "minutes": "minutes_played",
    }
    differences = []

    def _minutes_seconds(value: Any) -> int | None:
        if value in (None, ""):
            return None
        text = str(value)
        if ":" in text:
            parts = [int(part) for part in text.split(":")]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return round(float(text) * 60)

    for key in overlap:
        new_row = traditional[key]
        old_row = legacy[key]
        changed = {}
        for new_field, old_field in field_map.items():
            new_value = getattr(new_row, new_field)
            old_value = getattr(old_row, old_field)
            equal = (
                _minutes_seconds(new_value) == _minutes_seconds(old_value)
                if new_field == "minutes"
                else new_value == old_value
            )
            if not equal:
                changed[new_field] = {"traditional_v3": new_value, "gamelogs": old_value}
        if changed:
            differences.append({"key": key, "fields": changed})
    return {
        "overlap_rows": len(overlap),
        "traditional_only_rows": len(set(traditional) - set(legacy)),
        "legacy_only_rows": len(set(legacy) - set(traditional)),
        "different_rows": len(differences),
        "difference_examples": differences[:20],
    }


def build_reconciliation_report(
    db: Session,
    *,
    season: str,
    game_ids: Sequence[str],
    max_games: int,
) -> dict[str, Any]:
    game_ids = validate_game_bound(game_ids, max_games=max_games)
    schedules = (
        db.query(GameScheduleORM)
        .filter(GameScheduleORM.game_id.in_(game_ids))
        .all()
    )
    traditional = (
        db.query(PlayerGameFactORM)
        .filter(PlayerGameFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    advanced = (
        db.query(PlayerGameAdvancedFactORM)
        .filter(PlayerGameAdvancedFactORM.canonical_game_id.in_(game_ids))
        .all()
    )
    legacy = db.query(GameLogORM).filter(GameLogORM.game_id.in_(game_ids)).all()
    team_facts = (
        db.query(TeamGameStatsORM)
        .filter(TeamGameStatsORM.game_id.in_(game_ids))
        .all()
    )
    traditional_revisions = (
        db.query(PlayerGameFactRevisionORM)
        .filter(PlayerGameFactRevisionORM.canonical_game_id.in_(game_ids))
        .all()
    )
    advanced_revisions = (
        db.query(PlayerGameAdvancedFactRevisionORM)
        .filter(PlayerGameAdvancedFactRevisionORM.canonical_game_id.in_(game_ids))
        .all()
    )

    traditional_keys = [canonical_key(row) for row in traditional]
    advanced_keys = [canonical_key(row) for row in advanced]
    team_totals = {
        (str(row.game_id), int(row.team_id)): row.pts for row in team_facts
    }
    player_totals: dict[tuple[str, int], int] = defaultdict(int)
    for row in traditional:
        if row.points is not None:
            player_totals[(str(row.canonical_game_id), int(row.canonical_team_id))] += int(row.points)
    team_total_mismatches = [
        {
            "game_id": key[0],
            "team_id": key[1],
            "player_points": player_totals.get(key),
            "team_game_fact_points": score,
        }
        for key, score in sorted(team_totals.items())
        if score is None or player_totals.get(key) != int(score)
    ]
    expected_team_keys = {
        (str(row.game_id), int(row.team_id)) for row in schedules
    }
    missing_team_fact_keys = sorted(expected_team_keys - set(team_totals))
    traditional_counts = Counter(traditional_keys)
    advanced_counts = Counter(advanced_keys)
    duplicate_traditional = [key for key, count in traditional_counts.items() if count > 1]
    duplicate_advanced = [key for key, count in advanced_counts.items() if count > 1]
    identity_missing = sorted(set(traditional_keys) - set(advanced_keys))
    identity_unexpected = sorted(set(advanced_keys) - set(traditional_keys))
    parser_versions = Counter(row.parser_version for row in traditional_revisions)
    revision_grains = Counter(
        (row.source_name, row.source_row_key) for row in traditional_revisions
    )
    corrected_source_rows = sum(count > 1 for count in revision_grains.values())
    blocking = {
        "missing_schedule_pairs": max(0, len(game_ids) * 2 - len(schedules)),
        "duplicate_traditional_rows": len(duplicate_traditional),
        "duplicate_advanced_rows": len(duplicate_advanced),
        "advanced_identity_missing": len(identity_missing),
        "advanced_identity_unexpected": len(identity_unexpected),
        "missing_team_fact_rows": len(missing_team_fact_keys),
        "team_total_mismatches": len(team_total_mismatches),
    }
    return {
        "status": "passed" if not any(blocking.values()) else "failed",
        "season": season,
        "game_ids": game_ids,
        "blocking": blocking,
        "counts": {
            "schedule_rows": len(schedules),
            "team_game_fact_rows": len(team_facts),
            "traditional_facts": len(traditional),
            "advanced_facts": len(advanced),
            "legacy_gamelogs": len(legacy),
            "traditional_revisions": len(traditional_revisions),
            "advanced_revisions": len(advanced_revisions),
            "traditional_dnp": sum(row.participation_status == "did_not_play" for row in traditional),
            "traditional_unknown": sum(row.participation_status == "unknown" for row in traditional),
            "advanced_dnp": sum(row.participation_status == "did_not_play" for row in advanced),
            "corrected_source_rows": corrected_source_rows,
        },
        "traditional_parser_versions": dict(sorted(parser_versions.items())),
        "team_total_mismatches": team_total_mismatches[:20],
        "missing_team_fact_examples": missing_team_fact_keys[:20],
        "advanced_identity_missing_examples": identity_missing[:20],
        "advanced_identity_unexpected_examples": identity_unexpected[:20],
        "legacy_overlap": compare_overlap(traditional, legacy),
    }
