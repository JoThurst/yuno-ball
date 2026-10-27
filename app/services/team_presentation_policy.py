"""Opt-in small-sample display gates; never changes research/model readers."""
import math
from app.services.matchup_player_context_service import _utc


def _finite(row, fields):
    try:
        return all(getattr(row, field, None) is not None and math.isfinite(float(getattr(row, field))) for field in fields)
    except (TypeError, ValueError):
        return False


def _provenance(row, cutoff):
    feature = _utc(getattr(row, "feature_as_of", None))
    available = _utc(getattr(row, "data_available_at", None))
    tip = _utc(getattr(row, "scheduled_tipoff", None))
    return bool(feature and available and tip and available <= feature <= _utc(cutoff)
                and feature < tip and getattr(row, "source_run_id", None)
                and getattr(row, "source_latest_game_id", None)
                and getattr(row, "source_latest_game_date", None)
                and row.source_latest_game_date < row.game_date)


def qualified_small_sample(row, cutoff):
    flags = getattr(row, "missing_input_flags", {}) or {}
    if set(flags) != {"insufficient_window_games"} or not _provenance(row, cutoff):
        return False
    counts = [getattr(row, name, None) for name in ("window_games_used", "window_games_played", "season_games_used", "season_games_played", "window_size")]
    if any(value is None for value in counts):
        return False
    used, played, season_used, season_played, window = counts
    if not (1 <= used == played < window and season_used == season_played >= played
            and played == min(season_played, window)):
        return False
    if flags["insufficient_window_games"] != {"required": window, "available": played}:
        return False
    return _finite(row, ("pace_lastn", "off_rtg_lastn", "def_rtg_lastn", "net_rtg_season"))


def qualified_environment(row, teams, cutoff):
    if (getattr(row, "missing_input_flags", {}) or {}) != {"partial_team_snapshots": True}:
        return False
    home = teams.get((row.game_id, row.home_team_id))
    away = teams.get((row.game_id, row.away_team_id))
    if (not home or not away or home.team_id == away.team_id
            or home.is_home is not True or away.is_home is not False
            or home.opponent_team_id != away.team_id or away.opponent_team_id != home.team_id):
        return False
    for team in (home, away):
        if team.completeness_status != "complete" and not qualified_small_sample(team, cutoff):
            return False
        if not _provenance(team, cutoff):
            return False
        for key in ("game_id", "feature_as_of", "calculation_version", "window_size", "source_run_id", "season", "season_type", "scheduled_tipoff"):
            if getattr(team, key, None) != getattr(row, key, None):
                return False
    feature, available = _utc(row.feature_as_of), _utc(row.data_available_at)
    return bool(feature and available and available <= feature <= _utc(cutoff)
                and feature < _utc(row.scheduled_tipoff)
                and _finite(row, ("pace_projection", "scoring_env_index")))


def team_readout(row):
    if row is None:
        return {"label": "Team context", "value": None, "reason": "No cutoff-valid team history", "sample_size": 0}
    count = getattr(row, "season_games_used", None)
    delta = count is not None and count > getattr(row, "window_size", 10)
    value = getattr(row, "net_rtg_delta" if delta else "net_rtg_season", None)
    return {"label": "Recent minus season net rating" if delta else "Season net rating",
            "value": round(value, 1) if value is not None else None,
            "sample_size": count, "window_sample_size": getattr(row, "window_games_used", None),
            "completeness": getattr(row, "completeness_status", "unknown"),
            "reason": "Early-season estimate" if getattr(row, "completeness_status", None) == "partial" else "Descriptive team context"}
