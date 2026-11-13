"""Bounded, transient future-game context. No snapshots are published here."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.services.matchup_player_context_service import load_player_context
from app.services.official_availability_slate_service import build_game_official_availability
from app.services.team_presentation_policy import qualified_environment, qualified_small_sample, team_readout
from app.services.team_snapshot_service import (
    SOURCE_AVAILABILITY_LAG, SlateTeam, TeamSnapshotPublicationContext,
    _fetch_team_game_facts, build_game_environment_records, build_team_feature_records,
)
from app.utils.season_utils import season_for_date

EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
HORIZON_DAYS = 7
PREVIEW_VERSION = "future-matchup-preview-v1"


def _instant(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _schedule_pair(rows, *, target_date, season, away, home, as_of):
    """Require one exact, reciprocal, unresolved scheduled game."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row.get("game_id"))].append(row)
    matches = []
    for game_id, pair in grouped.items():
        if len(pair) != 2:
            continue
        h = next((row for row in pair if row.get("home_or_away") == "H"), None)
        a = next((row for row in pair if row.get("home_or_away") == "A"), None)
        if not h or not a:
            continue
        if str(h.get("team_abbreviation", "")).upper() != home or str(a.get("team_abbreviation", "")).upper() != away:
            continue
        try:
            tip = _instant(h["game_date"])
            away_tip = _instant(a["game_date"])
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
        if (any(row.get("season") != season or row.get("season_type") != "Regular Season"
                or row.get("game_date_precision") != "exact" or row.get("result") is not None
                or row.get("team_score") is not None or row.get("opponent_score") is not None
                for row in pair)
                or not str(game_id).lstrip("0").startswith("2")
                or h.get("team_id") == a.get("team_id")
                or h.get("opponent_team_id") != a.get("team_id")
                or a.get("opponent_team_id") != h.get("team_id")
                or tip != away_tip or tip <= as_of or tip.astimezone(EASTERN).date() != target_date):
            continue
        matches.append((game_id, h, a, tip))
    if len(matches) != 1:
        raise LookupError("No unambiguous scheduled matchup with an exact tipoff is available for this date.")
    return matches[0]


def _verified_facts(db, context, target_game_id, team_ids=None):
    """Filter mutable team facts through paired final schedule rows and a lag proxy."""
    facts = [f for f in _fetch_team_game_facts(db, context)
             if f.game_id != target_game_id and f.game_date < context.target_date
             and f.game_time + SOURCE_AVAILABILITY_LAG <= context.feature_as_of]
    ids = {f.game_id for f in facts}
    fact_keys = {(str(f.game_id), f.team_id) for f in facts}
    if team_ids:
        scheduled = (db.query(GameScheduleORM).filter(
            GameScheduleORM.season == context.season,
            GameScheduleORM.season_type == context.season_type,
            GameScheduleORM.team_id.in_(team_ids),
            GameScheduleORM.game_date < context.feature_as_of.replace(tzinfo=None),
            GameScheduleORM.result.in_(("W", "L")),
        ).all())
        for row in scheduled:
            if row.game_date_precision != "exact":
                return []
            if (row.game_date_precision == "exact" and _instant(row.game_date) + SOURCE_AVAILABILITY_LAG <= context.feature_as_of
                    and _instant(row.game_date).astimezone(EASTERN).date() < context.target_date
                    and (str(row.game_id), row.team_id) not in fact_keys):
                return []
    if not ids:
        return []
    rows = db.query(GameScheduleORM).filter(GameScheduleORM.game_id.in_(ids)).all()
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.game_id)].append(row)
    valid = set()
    for game_id, pair in groups.items():
        if len(pair) != 2:
            continue
        h = next((r for r in pair if r.home_or_away == "H"), None)
        a = next((r for r in pair if r.home_or_away == "A"), None)
        if not h or not a:
            continue
        if (h.team_id != a.team_id and h.opponent_team_id == a.team_id and a.opponent_team_id == h.team_id
                and h.season == a.season == context.season
                and h.season_type == a.season_type == context.season_type
                and h.game_date_precision == a.game_date_precision == "exact"
                and {h.result, a.result} == {"W", "L"}
                and _instant(h.game_date) == _instant(a.game_date)
                and _instant(h.game_date) + SOURCE_AVAILABILITY_LAG <= context.feature_as_of):
            valid.add(game_id)
    # Hiding a bad pair could turn incomplete history into an apparently
    # clean short sample, so withhold the entire team context instead.
    if any(f.team_id in (team_ids or ()) and f.game_id not in valid for f in facts):
        return []
    return [f for f in facts if f.game_id in valid]


def build_future_matchup_preview(target_date, *, away_abbreviation, home_abbreviation, season=None, now=None):
    """Return a current, non-replayable projection of a single scheduled future game."""
    as_of = _instant(now or datetime.now(UTC))
    today = as_of.astimezone(EASTERN).date()
    if not today < target_date <= today + timedelta(days=HORIZON_DAYS):
        raise LookupError("Future previews are available only for scheduled games within the next seven Eastern calendar days.")
    actual_season = season_for_date(target_date)
    if season and season != actual_season:
        raise LookupError("The requested season does not match the scheduled date.")
    season = actual_season
    with get_db_context() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        game_id, home, away, tip = _schedule_pair(
            GameScheduleORM.get_by_date(target_date, db=db), target_date=target_date,
            season=season, away=away_abbreviation.upper(), home=home_abbreviation.upper(), as_of=as_of,
        )
        context = TeamSnapshotPublicationContext(season=season, season_type="Regular Season",
            target_date=target_date, feature_as_of=as_of, calculation_version=PREVIEW_VERSION,
            source_run_id="transient-preview")
        facts = _verified_facts(db, context, game_id, {home["team_id"], away["team_id"]})
        slate = [SlateTeam(game_id, home["team_id"], away["team_id"], tip, True),
                 SlateTeam(game_id, away["team_id"], home["team_id"], tip, False)]
        records = build_team_feature_records(context, slate, facts)
        rows = [SimpleNamespace(**record) for record in records]
        admissible = [row for row in rows if (row.completeness_status == "complete" or qualified_small_sample(row, as_of))]
        environment_records = build_game_environment_records(context, records)
        environment = None
        if environment_records:
            candidate = SimpleNamespace(**environment_records[0])
            pair = {(row.game_id, row.team_id): row for row in admissible}
            if (candidate.completeness_status == "complete" and len(admissible) == 2
                    or qualified_environment(candidate, pair, as_of)):
                environment = {"pace": candidate.pace_projection, "scoring_index": candidate.scoring_env_index,
                               "completeness": candidate.completeness_status}
        availability = build_game_official_availability(game_id, scheduled_tipoff=tip, db=db, requested_cutoff=as_of)
        players = load_player_context(db, target_date=target_date, cutoff=as_of, season=season,
                                      team_ids={home["team_id"], away["team_id"]}, limit=4)
        team_context = {row.team_id: team_readout(row) for row in admissible}
        return {"preview": {"version": PREVIEW_VERSION, "as_of": as_of.isoformat(),
            "target_game_date": target_date.isoformat(), "tipoff": tip.isoformat(), "game_id": game_id,
            "home": home, "away": away, "season": season, "environment": environment,
            "team_context": team_context, "players": players, "availability": availability,
            "source_game_ids": sorted({f.game_id for f in facts}),
            "source": "team_game_stats and game_schedule; scheduled tipoff plus six hours availability proxy",
            "stale": None, "completeness": "partial" if environment is None else environment["completeness"]}}
