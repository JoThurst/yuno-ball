"""Audit the available pregame inputs for the Program E Rotation Shock track."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine


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
        description="Run a read-only Program E Rotation Shock input audit"
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--season-type", default="Regular Season")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    return parser.parse_args()


def _scalar(db, sql: str, params: dict) -> int:
    value = db.execute(text(sql), params).scalar()
    return int(value or 0)


def run_audit(args: argparse.Namespace) -> dict:
    default_start, default_end = _season_bounds(args.season)
    start_date = args.start_date or default_start
    end_date = args.end_date or default_end
    if start_date > end_date:
        raise ValueError("start date must not be after end date")
    params = {
        "season": args.season,
        "season_type": args.season_type,
        "start_date": start_date,
        "end_date": end_date,
    }

    with engine.connect() as db:
        player_facts = {
            "rows": _scalar(db, "select count(*) from player_game_facts where season=:season", params),
            "complete_rows": _scalar(db, """select count(*) from player_game_facts
                where season=:season and completeness_status='complete'""", params),
            "played_rows": _scalar(db, """select count(*) from player_game_facts
                where season=:season and participation_status='played'""", params),
            "known_starter_or_bench_rows": _scalar(db, """select count(*) from player_game_facts
                where season=:season and starter_status in ('starter','bench')""", params),
            "minutes_present_rows": _scalar(db, """select count(*) from player_game_facts
                where season=:season and minutes is not null""", params),
        }
        advanced_facts = {
            "rows": _scalar(db, "select count(*) from player_game_advanced_facts where season=:season", params),
            "complete_rows": _scalar(db, """select count(*) from player_game_advanced_facts
                where season=:season and completeness_status='complete'""", params),
            "usage_present_rows": _scalar(db, """select count(*) from player_game_advanced_facts
                where season=:season and usage_percentage is not null""", params),
            "assist_percentage_present_rows": _scalar(db, """select count(*) from player_game_advanced_facts
                where season=:season and assist_percentage is not null""", params),
            "traditional_advanced_key_matches": _scalar(db, """select count(*)
                from player_game_facts p
                join player_game_advanced_facts a
                  on a.canonical_game_id=p.canonical_game_id
                 and a.canonical_player_id=p.canonical_player_id
                 and a.canonical_team_id=p.canonical_team_id
                where p.season=:season and a.season=:season""", params),
        }
        starter_evidence = {
            "rows": _scalar(db, """select count(*) from player_game_starter_evidence
                where season=:season and season_type=:season_type""", params),
            "games": _scalar(db, """select count(distinct canonical_game_id)
                from player_game_starter_evidence
                where season=:season and season_type=:season_type
                  and canonical_game_id is not null""", params),
            "explicit_starter_rows": _scalar(db, """select count(*)
                from player_game_starter_evidence
                where season=:season and season_type=:season_type
                  and starter_status='starter'""", params),
            "sources": [
                dict(row._mapping)
                for row in db.execute(text("""select source_name, count(*) as rows
                    from player_game_starter_evidence
                    where season=:season and season_type=:season_type
                    group by source_name order by source_name"""), params)
            ],
            "complete_games": _scalar(db, """
                select count(*) from (
                    select canonical_game_id,
                           count(*) filter (where starter_status='starter') as starter_rows,
                           count(distinct canonical_team_id) as team_count
                    from player_game_starter_evidence
                    where season=:season and season_type=:season_type
                      and canonical_game_id is not null
                    group by canonical_game_id
                ) coverage
                where starter_rows=10 and team_count=2
            """, params),
            "partial_games": _scalar(db, """
                select count(*) from (
                    select canonical_game_id,
                           count(*) filter (where starter_status='starter') as starter_rows
                    from player_game_starter_evidence
                    where season=:season and season_type=:season_type
                      and canonical_game_id is not null
                    group by canonical_game_id
                ) coverage
                where starter_rows > 0 and starter_rows <> 10
            """, params),
            "completed_schedule_games": _scalar(db, """
                select count(distinct game_id) from game_schedule
                where season=:season and season_type=:season_type
                  and result is not null
            """, params),
        }
        starter_evidence["missing_completed_games"] = max(
            0,
            starter_evidence["completed_schedule_games"]
            - starter_evidence["complete_games"],
        )
        availability = {
            "rows": _scalar(db, """select count(*) from availability_observations
                where game_date between :start_date and :end_date""", params),
            "resolved_player_team_game_rows": _scalar(db, """select count(*) from availability_observations
                where game_date between :start_date and :end_date
                  and player_id is not null and team_id is not null and game_id is not null""", params),
            "canonical_schedule_join_rows": _scalar(db, """select count(*)
                from availability_observations a
                join game_schedule s
                  on s.game_id=a.game_id and s.team_id=a.team_id
                 and s.season=:season and s.season_type=:season_type
                where a.game_date between :start_date and :end_date""", params),
        }
        availability["pregame_timestamp_rows"] = _scalar(
            db,
            """select count(*)
               from availability_observations a
               join game_schedule s
                 on s.game_id=a.game_id and s.team_id=a.team_id
                and s.season=:season and s.season_type=:season_type
               where a.game_date between :start_date and :end_date
                 and a.report_published_at <= (s.game_date at time zone 'UTC')""",
            params,
        )
        availability["post_tipoff_or_missing_cutoff_rows"] = _scalar(
            db,
            """select count(*)
               from availability_observations a
               left join game_schedule s
                 on s.game_id=a.game_id and s.team_id=a.team_id
                and s.season=:season and s.season_type=:season_type
               where a.game_date between :start_date and :end_date
                 and (s.game_id is null
                      or a.report_published_at > (s.game_date at time zone 'UTC'))""",
            params,
        )
        availability["pregame_game_count"] = _scalar(
            db,
            """select count(distinct a.game_id)
               from availability_observations a
               join game_schedule s
                 on s.game_id=a.game_id and s.team_id=a.team_id
                and s.season=:season and s.season_type=:season_type
               where a.game_date between :start_date and :end_date
                 and a.report_published_at <= (s.game_date at time zone 'UTC')""",
            params,
        )
        availability["pregame_game_team_count"] = _scalar(
            db,
            """select count(distinct (a.game_id, a.team_id))
               from availability_observations a
               join game_schedule s
                 on s.game_id=a.game_id and s.team_id=a.team_id
                and s.season=:season and s.season_type=:season_type
               where a.game_date between :start_date and :end_date
                 and a.report_published_at <= (s.game_date at time zone 'UTC')""",
            params,
        )
        availability["pregame_non_available_game_count"] = _scalar(
            db,
            """select count(distinct a.game_id)
               from availability_observations a
               join game_schedule s
                 on s.game_id=a.game_id and s.team_id=a.team_id
                and s.season=:season and s.season_type=:season_type
               where a.game_date between :start_date and :end_date
                 and a.report_published_at <= (s.game_date at time zone 'UTC')
                 and a.status in ('Probable','Questionable','Doubtful','Out')""",
            params,
        )
        availability["completed_game_count"] = _scalar(
            db,
            """select count(distinct game_id) from game_schedule
               where season=:season and season_type=:season_type
                 and result is not null""",
            params,
        )
        availability["completed_game_team_count"] = _scalar(
            db,
            """select count(*) from (
                    select distinct game_id, team_id from game_schedule
                    where season=:season and season_type=:season_type
                      and result is not null
                ) scheduled""",
            params,
        )
        availability["pregame_reported_game_team_count"] = _scalar(
            db,
            """select count(*) from (
                select distinct a.game_id, a.team_id
                from availability_observations a
                join game_schedule s on s.game_id=a.game_id and s.team_id=a.team_id
                where s.season=:season and s.season_type=:season_type
                  and s.result is not null
                  and a.report_published_at <= (s.game_date at time zone 'UTC')
                union
                select distinct t.game_id, t.team_id
                from team_report_submission_status t
                join game_schedule s on s.game_id=t.game_id and s.team_id=t.team_id
                where s.season=:season and s.season_type=:season_type
                  and s.result is not null
                  and t.report_published_at <= (s.game_date at time zone 'UTC')
            ) reported""",
            params,
        )
        availability["unreported_completed_game_team_count"] = _scalar(
            db,
            """select count(*) from (
                    select distinct game_id, team_id from game_schedule
                    where season=:season and season_type=:season_type
                      and result is not null
                ) scheduled
                left join (
                    select distinct a.game_id, a.team_id
                    from availability_observations a
                    join game_schedule s on s.game_id=a.game_id and s.team_id=a.team_id
                    where s.season=:season and s.season_type=:season_type
                      and s.result is not null
                      and a.report_published_at <= (s.game_date at time zone 'UTC')
                    union
                    select distinct t.game_id, t.team_id
                    from team_report_submission_status t
                    join game_schedule s on s.game_id=t.game_id and s.team_id=t.team_id
                    where s.season=:season and s.season_type=:season_type
                      and s.result is not null
                      and t.report_published_at <= (s.game_date at time zone 'UTC')
                ) reported using (game_id, team_id)
                where reported.game_id is null""",
            params,
        )
        roster_rows = _scalar(db, "select count(*) from roster where season=:season", params)
        precision_rows = [
            dict(row._mapping)
            for row in db.execute(text("""select source_time_precision, count(*) as rows
                from availability_observations
                where game_date between :start_date and :end_date
                group by source_time_precision order by source_time_precision"""), params)
        ]
        rotation_tables = [
            row[0]
            for row in db.execute(text("""select table_name from information_schema.tables
                where table_schema='public'
                  and (table_name ilike '%lineup%' or table_name ilike '%rotation%')
                order by table_name"""))
        ]

    hard_blockers = []
    if player_facts["rows"] and not player_facts["known_starter_or_bench_rows"]:
        hard_blockers.append("starter_status is unknown for every canonical player-game fact")
    if not rotation_tables:
        hard_blockers.append("no lineup or rotation table is present")
    hard_blockers.append("expected pregame minutes are not stored as an observation")

    return {
        "mode": "read-only-audit",
        "research_track": "rotation_shock",
        "season": args.season,
        "season_type": args.season_type,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "player_game_facts": player_facts,
        "advanced_player_game_facts": advanced_facts,
        "starter_evidence": starter_evidence,
        "availability_observations": availability,
        "availability_time_precision": precision_rows,
        "roster_rows": roster_rows,
        "lineup_or_rotation_tables": rotation_tables,
        "researchable_v01_inputs": [
            "official pregame availability status and report timing",
            "prior actual minutes as a role baseline",
            "prior usage percentage",
            "prior assist percentage as a creation proxy",
        ],
        "blocked_or_unvalidated_inputs": hard_blockers + [
            "replacement quality requires an explicit pregame baseline contract",
            "lineup continuity cannot be measured without lineup or stint facts",
        ],
        "coverage_contract": {
            "starter_complete_game_rule": (
                "exactly ten explicit starter rows across both teams; no inference "
                "from minutes or participation"
            ),
            "availability_absent_report": "unknown",
            "availability_rule": (
                "Only a pregame observation or explicit team submission is reported "
                "as covered; absence is never converted to Available."
            ),
        },
        "writes_performed": False,
    }


def main() -> int:
    print(json.dumps(run_audit(parse_args()), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
