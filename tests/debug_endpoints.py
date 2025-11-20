# -*- coding: utf-8 -*-
"""Minimal helper script to inspect NBA Stats endpoints from the CLI."""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nba_api.stats.endpoints import ScoreboardV2, leaguestandingsv3  # noqa: E402
from nba_api.stats.endpoints._base import Endpoint  # noqa: E402
from app.utils.fetch.api_utils import get_api_config  # noqa: E402

logger = logging.getLogger("debug_endpoints")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class SafeScoreboardV2(ScoreboardV2):
    """ScoreboardV2 variant that tolerates missing datasets (e.g. WinProbability)."""

    def load_response(self):
        data_sets = self.nba_response.get_data_sets()
        self.data_sets = [Endpoint.DataSet(data=data_set) for data_set in data_sets.values()]

        def safe_dataset(name):
            return Endpoint.DataSet(data=data_sets.get(name, {"headers": [], "data": []}))

        self.available = safe_dataset("Available")
        self.east_conf_standings_by_day = safe_dataset("EastConfStandingsByDay")
        self.game_header = safe_dataset("GameHeader")
        self.last_meeting = safe_dataset("LastMeeting")
        self.line_score = safe_dataset("LineScore")
        self.series_standings = safe_dataset("SeriesStandings")
        self.team_leaders = safe_dataset("TeamLeaders")
        self.ticket_links = safe_dataset("TicketLinks")
        self.west_conf_standings_by_day = safe_dataset("WestConfStandingsByDay")
        self.win_probability = safe_dataset("WinProbability")


def dataset_to_dicts(data_set):
    dataset = data_set.get_dict()
    headers = dataset.get("headers") or []
    rows = dataset.get("data") or []
    return [dict(zip(headers, row)) for row in rows]


def format_win_pct(value):
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return value
    return f"{pct:.3f}".lstrip("0")


def print_standings(title, rows):
    logger.info("\n%s (%d teams)", title, len(rows))
    if not rows:
        logger.info("  [no records]")
        return
    for entry in rows:
        team = entry.get("TEAM") or entry.get("TeamName") or entry.get("TeamSlug") or "Unknown"
        wins = entry.get("W") or entry.get("WINS") or 0
        losses = entry.get("L") or entry.get("LOSSES") or 0
        win_pct = format_win_pct(entry.get("W_PCT") or entry.get("WinPCT"))
        logger.info("  %-25s %3s-%-3s  win_pct=%s", team, wins, losses, win_pct)


def print_games(rows):
    logger.info("\nGames (%d)", len(rows))
    if not rows:
        logger.info("  [no games scheduled]")
        return
    for entry in rows:
        logger.info(
            "  %s | %s @ %s | status=%s",
            entry.get("GAME_ID"),
            entry.get("VISITOR_TEAM_ID"),
            entry.get("HOME_TEAM_ID"),
            entry.get("GAME_STATUS_TEXT"),
        )


def debug_scoreboard_v2(game_date=None, day_offset=0, raw=False):
    config = get_api_config()
    target_date = game_date or datetime.now().strftime("%Y-%m-%d")
    logger.info("Requesting ScoreboardV2 for %s (DayOffset=%s)", target_date, day_offset)

    start = time.time()
    scoreboard = SafeScoreboardV2(
        game_date=target_date,
        day_offset=day_offset,
        league_id="00",
        proxy=config.get("proxy"),
        headers=config.get("headers"),
        timeout=config.get("timeout", 30),
    )
    elapsed = time.time() - start
    logger.info("ScoreboardV2 responded in %.2fs", elapsed)

    east = dataset_to_dicts(scoreboard.east_conf_standings_by_day)
    west = dataset_to_dicts(scoreboard.west_conf_standings_by_day)
    games = dataset_to_dicts(scoreboard.game_header)
    line_scores = dataset_to_dicts(scoreboard.line_score)

    print_standings("Eastern Conference", east)
    print_standings("Western Conference", west)
    print_games(games)

    logger.info("\nLine score entries: %d", len(line_scores))
    if raw:
        logger.info("\nRaw Scoreboard payload:\n%s", json.dumps(scoreboard.nba_response.get_dict(), indent=2))

    return {
        "east": east,
        "west": west,
        "games": games,
        "line_scores": line_scores,
    }


def debug_league_standings(season=None, season_type="Regular Season"):
    config = get_api_config()
    season = season or derive_current_season()
    logger.info("Requesting LeagueStandingsV3 for season=%s season_type=%s", season, season_type)

    start = time.time()
    standings = leaguestandingsv3.LeagueStandingsV3(
        league_id="00",
        season=season,
        season_type=season_type,
        proxy=config.get("proxy"),
        headers=config.get("headers"),
        timeout=config.get("timeout", 30),
    )
    elapsed = time.time() - start
    logger.info("LeagueStandingsV3 responded in %.2fs", elapsed)

    dataset = standings.standings.get_dict()
    headers = dataset.get("headers") or []
    rows = dataset.get("data") or []

    east = []
    west = []
    for row in rows:
        entry = dict(zip(headers, row))
        conference = entry.get("Conference")
        if conference and str(conference).lower().startswith("east"):
            east.append(entry)
        elif conference and str(conference).lower().startswith("west"):
            west.append(entry)

    print_standings(f"LeagueStandingsV3 East ({season})", east)
    print_standings(f"LeagueStandingsV3 West ({season})", west)

    return {"east": east, "west": west}


def derive_current_season():
    now = datetime.now()
    start_year = now.year if now.month >= 10 else now.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def main():
    parser = argparse.ArgumentParser(description="Inspect NBA Scoreboard and standings endpoints.")
    parser.add_argument("--scoreboard-date", help="Date (YYYY-MM-DD) for ScoreboardV2. Defaults to today.")
    parser.add_argument("--day-offset", type=int, default=0, help="DayOffset parameter for ScoreboardV2.")
    parser.add_argument("--raw", action="store_true", help="Dump the full ScoreboardV2 JSON response.")
    parser.add_argument(
        "--league-standings",
        action="store_true",
        help="Also fetch LeagueStandingsV3 for comparison.",
    )
    parser.add_argument("--season", help="Season string for LeagueStandingsV3 (e.g. 2024-25). Defaults to current season.")
    parser.add_argument(
        "--season-type",
        default="Regular Season",
        choices=["Pre Season", "Regular Season"],
        help="SeasonType for LeagueStandingsV3.",
    )
    args = parser.parse_args()

    debug_scoreboard_v2(game_date=args.scoreboard_date, day_offset=args.day_offset, raw=args.raw)

    if args.league_standings:
        debug_league_standings(season=args.season, season_type=args.season_type)


if __name__ == "__main__":
    main()
