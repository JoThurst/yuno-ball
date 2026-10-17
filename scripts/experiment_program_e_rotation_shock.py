"""Run a read-only, observed-status Rotation Shock shadow experiment."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.services.metric_research_service import (
    RotationShockObservation,
    RotationShockPlayerObservation,
    calculate_rotation_shock,
)


RISK_STATUSES = {"Questionable", "Doubtful", "Out"}


def _season_bounds(season: str) -> tuple[date, date]:
    try:
        start_year = int(season[:4])
        if season[4] != "-":
            raise ValueError
    except (ValueError, IndexError):
        raise ValueError("season must use YYYY-YY format") from None
    return date(start_year, 10, 1), date(start_year + 1, 6, 30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a read-only observed-status Rotation Shock experiment"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--examples", type=int, default=5)
    return parser.parse_args()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes(value: Any) -> float | None:
    if value in (None, "", "0:00", "00:00"):
        return 0.0 if value in ("0:00", "00:00") else None
    text_value = str(value)
    pieces = text_value.split(":")
    try:
        if len(pieces) == 2:
            return int(pieces[0]) + int(pieces[1]) / 60
        if len(pieces) == 3:
            return int(pieces[0]) * 60 + int(pieces[1]) + int(pieces[2]) / 60
        return float(text_value)
    except (TypeError, ValueError):
        return None


def _target_rows(db, args: argparse.Namespace, start_date: date, end_date: date) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            with target_schedule as (
                select s.game_id, s.team_id, s.season, s.season_type, s.game_date
                from game_schedule s
                where s.season = :season
                  and s.season_type = :season_type
                  and s.game_date::date between :start_date and :end_date
            ), latest_reports as (
                select distinct on (a.game_id, a.team_id, a.player_id)
                    a.game_id,
                    a.team_id,
                    a.player_id,
                    a.reported_player_name,
                    a.status,
                    a.report_published_at,
                    s.season,
                    s.season_type,
                    s.game_date as scheduled_tipoff
                from availability_observations a
                join target_schedule s
                  on s.game_id = a.game_id
                 and s.team_id = a.team_id
                where a.player_id is not null
                  and a.report_published_at < (s.game_date at time zone 'UTC') - interval '1 second'
                order by a.game_id, a.team_id, a.player_id,
                         a.report_published_at desc, a.observation_id desc
            )
            select * from latest_reports
            order by scheduled_tipoff, game_id, team_id, player_id
            """
        ),
        {
            "season": args.season,
            "season_type": args.season_type,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return [dict(row._mapping) for row in rows]


def _prior_facts(db, args: argparse.Namespace) -> dict[tuple[int, int], list[dict[str, Any]]]:
    rows = db.execute(
        text(
            """
            select p.canonical_player_id as player_id,
                   p.canonical_team_id as team_id,
                   p.game_date,
                   p.minutes,
                   a.usage_percentage,
                   a.assist_percentage
            from player_game_facts p
            left join player_game_advanced_facts a
              on a.canonical_game_id = p.canonical_game_id
             and a.canonical_player_id = p.canonical_player_id
             and a.canonical_team_id = p.canonical_team_id
            where p.season = :season
              and p.season_type = :season_type
              and p.completeness_status = 'complete'
              and p.participation_status = 'played'
            order by p.canonical_player_id, p.canonical_team_id, p.game_date desc,
                     p.canonical_game_id desc
            """
        ),
        {"season": args.season, "season_type": args.season_type},
    )
    facts: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        facts[(int(row.player_id), int(row.team_id))].append(dict(row._mapping))
    return facts


def _find_prior(
    facts: dict[tuple[int, int], list[dict[str, Any]]],
    player_id: int,
    team_id: int,
    target_date: date,
) -> dict[str, Any] | None:
    for row in facts.get((player_id, team_id), []):
        if row["game_date"] < target_date:
            return row
    return None


def _panel(
    rows: list[dict[str, Any]],
    facts: dict[tuple[int, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    first = rows[0]
    scheduled_tipoff = _as_utc(first["scheduled_tipoff"])
    feature_as_of = scheduled_tipoff - timedelta(seconds=1)
    latest_report = max(_as_utc(row["report_published_at"]) for row in rows)
    risk_rows = [row for row in rows if row["status"] in RISK_STATUSES]
    observations = []
    baseline_missing = Counter()
    target_date = scheduled_tipoff.date()
    for row in risk_rows:
        prior = _find_prior(facts, int(row["player_id"]), int(row["team_id"]), target_date)
        prior_minutes = _minutes(prior["minutes"]) if prior else None
        prior_usage = _numeric(prior["usage_percentage"]) if prior else None
        prior_assist = _numeric(prior["assist_percentage"]) if prior else None
        for field_name, value in (
            ("prior_minutes", prior_minutes),
            ("prior_usage_percentage", prior_usage),
            ("prior_assist_percentage", prior_assist),
        ):
            if value is None:
                baseline_missing[field_name] += 1
        observations.append(
            RotationShockPlayerObservation(
                player_id=int(row["player_id"]),
                player_name=str(row["reported_player_name"]),
                status=str(row["status"]),
                prior_minutes=prior_minutes,
                prior_usage_percentage=prior_usage,
                prior_assist_percentage=prior_assist,
                report_published_at=_as_utc(row["report_published_at"]),
            )
        )

    result = None
    if risk_rows:
        result = calculate_rotation_shock(
            RotationShockObservation(
                game_id=str(first["game_id"]),
                team_id=int(first["team_id"]),
                season=str(first["season"]),
                season_type=str(first["season_type"]),
                feature_as_of=feature_as_of,
                data_available_at=latest_report,
                scheduled_tipoff=scheduled_tipoff,
                availability_evidence_status="complete",
                players=tuple(observations),
            )
        ).as_dict()

    return {
        "game_id": str(first["game_id"]),
        "team_id": int(first["team_id"]),
        "season": str(first["season"]),
        "season_type": str(first["season_type"]),
        "scheduled_tipoff": scheduled_tipoff.isoformat(),
        "feature_as_of": feature_as_of.isoformat(),
        "observed_player_rows": len(rows),
        "observed_risk_player_rows": len(risk_rows),
        "risk_status_counts": dict(sorted(Counter(row["status"] for row in risk_rows).items())),
        "baseline_missing": dict(sorted(baseline_missing.items())),
        "result": result,
    }


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    if args.examples < 1:
        raise ValueError("--examples must be at least 1")
    default_start, default_end = _season_bounds(args.season)
    start_date = args.start_date or default_start
    end_date = args.end_date or default_end
    if start_date > end_date:
        raise ValueError("start date must not be after end date")

    with engine.connect() as db:
        target_rows = _target_rows(db, args, start_date, end_date)
        facts = _prior_facts(db, args)

    rows_by_panel: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in target_rows:
        rows_by_panel[(str(row["game_id"]), int(row["team_id"]))].append(row)
    panels = [_panel(rows, facts) for rows in rows_by_panel.values()]
    panels.sort(key=lambda row: (row["scheduled_tipoff"], row["game_id"], row["team_id"]))

    scored = [
        panel for panel in panels
        if panel["result"] and panel["result"]["completeness_status"] == "complete"
    ]
    withheld = [panel for panel in panels if panel["result"] and panel["result"]["completeness_status"] != "complete"]
    observed_zero_risk = [panel for panel in panels if not panel["observed_risk_player_rows"]]
    values = [panel["result"]["value"] for panel in scored]
    values.sort()
    examples = []
    if scored:
        scored_by_value = sorted(scored, key=lambda panel: panel["result"]["value"])
        indexes = sorted({0, len(scored_by_value) // 2, len(scored_by_value) - 1})
        examples = scored_by_value[: args.examples]
        if args.examples >= 3:
            examples = [scored_by_value[index] for index in indexes]

    return {
        "mode": "read-only-experiment",
        "research_track": "rotation_shock",
        "metric_id": "rotation_shock_exposure",
        "version": "rotation-shock-v0.1",
        "season": args.season,
        "season_type": args.season_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "reference_scope": "latest explicit pregame status per player, with prior same-team played fact only",
        "feature_cutoff": "one second before canonical scheduled tipoff; target-game facts are never read",
        "observed_status_scope": "Only explicit Questionable, Doubtful, and Out rows are scored; absent rows are not treated as Available.",
        "target_games": len({panel["game_id"] for panel in panels}),
        "target_game_team_panels": len(panels),
        "panels_with_pregame_observations": len(panels),
        "panels_with_observed_risk_status": len([panel for panel in panels if panel["observed_risk_player_rows"]]),
        "scoreable_panels": len(scored),
        "withheld_panels": len(withheld),
        "observed_zero_risk_panels": len(observed_zero_risk),
        "risk_status_counts": dict(sorted(Counter(
            status
            for panel in panels
            for status, count in panel["risk_status_counts"].items()
            for _ in range(count)
        ).items())),
        "score_summary": {
            "min": min(values) if values else None,
            "median": values[len(values) // 2] if values else None,
            "max": max(values) if values else None,
            "mean": round(sum(values) / len(values), 4) if values else None,
        },
        "baseline_missing_counts": dict(sorted(Counter(
            field
            for panel in panels
            for field, count in panel["baseline_missing"].items()
            for _ in range(count)
        ).items())),
        "examples": examples,
        "interpretation": "This is a descriptive observed-risk shadow replay, not a complete injury census, expected-minutes model, lineup model, or production feature.",
        "writes_performed": False,
    }


def main() -> int:
    print(json.dumps(run_experiment(parse_args()), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
