"""Read-only descriptive player history; no roster or availability inference."""
from collections import defaultdict
from datetime import timezone
import math

from app.models.player_game_fact_sqlalchemy import PlayerGameFactORM
from app.models.player_sqlalchemy import PlayerORM

VERSION = "matchup-player-context-v1"
STATS = {"points": (10, 20, 30), "rebounds_total": (5, 10), "assists": (5, 10)}


def _number(value):
    if value is None:
        return None
    try:
        if ":" in str(value):
            parts = str(value).split(":")
            if len(parts) == 2:
                minutes, seconds = parts
                value = float(minutes) + float(seconds) / 60
            elif len(parts) == 3:
                hours, minutes, seconds = parts
                value = float(hours) * 60 + float(minutes) + float(seconds) / 60
            else:
                return None
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (ValueError, TypeError):
        return None


def _utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def build_player_context(rows, *, target_date, cutoff, team_ids, names=None, limit=5):
    """Conservative selection: later-selected corrections withhold the row.

    Team grouping means last observed team in eligible facts, never confirmed
    target-game membership. All played season history follows that player.
    """
    histories = defaultdict(list)
    withheld_players = set()
    for row in rows:
        available = _utc(getattr(row, "data_available_at", None))
        selected = _utc(getattr(row, "selected_at", None))
        if (row.game_date < target_date and row.canonical_player_id is not None
                and (available is None or selected is None
                     or available > _utc(cutoff) or selected > _utc(cutoff))):
            # The current canonical projection cannot reconstruct an earlier
            # revision. Omitting just this game could fabricate a streak or a
            # season average, so withhold the player's entire history.
            withheld_players.add(row.canonical_player_id)
        if (row.game_date >= target_date or available is None or selected is None
                or available > _utc(cutoff) or selected > _utc(cutoff)
                or row.canonical_player_id is None or row.canonical_team_id is None):
            continue
        histories[row.canonical_player_id].append(row)
    result = {team_id: [] for team_id in team_ids}
    for player_id, history in histories.items():
        if player_id in withheld_players:
            continue
        history.sort(key=lambda r: (r.game_date, r.canonical_game_id), reverse=True)
        latest_date = history[0].game_date
        latest_teams = {r.canonical_team_id for r in history if r.game_date == latest_date}
        if len(latest_teams) != 1:
            continue
        team_id = history[0].canonical_team_id
        if team_id not in result:
            continue
        played = [r for r in history if r.participation_status == "played"]
        if not played:
            continue
        # The projection carries a date, not a cutoff-safe game timestamp.
        # A same-day doubleheader has no reliable ordering here, so an arbitrary
        # game-id tie break must not determine streaks or recent windows.
        ambiguous_order = len({row.game_date for row in played}) != len(played)
        averages, frequencies, streaks = {}, [], []
        for stat in (*STATS, "minutes"):
            values = [_number(getattr(r, stat)) for r in played]
            known = [v for v in values if v is not None]
            averages[stat] = {"value": round(sum(known) / len(known), 1) if known else None,
                              "sample_size": len(known), "appearances": len(played)}
            for threshold in (() if ambiguous_order else STATS.get(stat, ())):
                recent = values[:10]
                denominator = sum(v is not None for v in recent)
                frequencies.append({"stat": stat, "threshold": threshold,
                                    "hits": sum(v is not None and v >= threshold for v in recent),
                                    "denominator": denominator, "appearances": len(recent)})
                count = 0
                for value in values:
                    if value is None or value < threshold:
                        break
                    count += 1
                if count >= 3:
                    streaks.append({"stat": stat, "threshold": threshold, "length": count})
        result[team_id].append({
            "player_id": player_id, "player_name": (names or {}).get(player_id) or f"Player {player_id}",
            "team_id": team_id, "membership_status": "last_observed_only",
            "membership_as_of": history[0].game_date.isoformat(), "appearances": len(played),
            "averages": averages, "frequencies": frequencies, "streaks": streaks,
            "recent_lines": [] if ambiguous_order else [{"game_date": r.game_date.isoformat(), "game_id": r.canonical_game_id,
                              "points": _number(r.points), "rebounds_total": _number(r.rebounds_total),
                              "assists": _number(r.assists), "minutes": _number(r.minutes)} for r in played[:3]],
            "recent_history_reason": "same_day_game_order_unknown" if ambiguous_order else None,
            "source": "canonical_player_game_facts", "as_of": cutoff.isoformat(),
            "calculation_version": VERSION, "completeness": "available_rows_only",
            "is_stale": None, "source_names": sorted({r.source_name for r in played}),
        })
    for team_id in result:
        result[team_id].sort(key=lambda p: (-(p["averages"]["minutes"]["value"] or 0), p["player_id"]))
        result[team_id] = result[team_id][:limit]
    return result


def load_player_context(db, *, target_date, cutoff, season, team_ids, limit=5):
    # Read the whole bounded season to avoid assigning traded players from an
    # older row merely because the latest observed team is outside this slate.
    rows = db.query(PlayerGameFactORM).filter(
        PlayerGameFactORM.season == season,
        PlayerGameFactORM.season_type == "Regular Season",
        PlayerGameFactORM.game_date < target_date,
    ).all()
    ids = {r.canonical_player_id for r in rows if r.canonical_player_id is not None}
    names = dict(db.query(PlayerORM.player_id, PlayerORM.name).filter(PlayerORM.player_id.in_(ids)).all()) if ids else {}
    return build_player_context(rows, target_date=target_date, cutoff=cutoff,
                                team_ids=team_ids, names=names, limit=limit)
