"""
Script to generate a comprehensive report for today's NBA games.

This script creates a text file with streaks, heat index, and stat windows
for all players playing in today's games.

Usage:
    python todays_games_report.py                    # Generate report for today
    python todays_games_report.py --output report.txt # Custom output file
    python todays_games_report.py --date 2025-11-25  # Specific date
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set

# Add project root to Python path
# Go up one level from scripts/ to project root
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root)) 

from app.database import get_db_context
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM, RosterORM
from app.models.consecutive_streak_sqlalchemy import ConsecutiveStreakORM
from app.models.player_heat_index_sqlalchemy import PlayerHeatIndexORM
from app.models.player_stat_window_sqlalchemy import PlayerStatWindowORM
from app.models.player_consistency_sqlalchemy import PlayerConsistencyORM
from app.models.player_analytics_snapshot_sqlalchemy import (
    PlayerConsecutiveStreakSnapshotORM,
    PlayerConsistencySnapshotORM,
    PlayerHeatIndexSnapshotORM,
    PlayerStatWindowSnapshotORM,
)
from app.services.heat_index_service import HeatIndexService
from app.services.player_snapshot_service import (
    complete_snapshot_history_exists,
    feature_cutoff_for_slate,
    load_complete_snapshot_at_cutoff,
    load_latest_complete_snapshot,
)


from app.utils.season_utils import get_current_season


def get_players_from_games(games: List[Dict], season: str, db) -> Dict[int, Dict]:
    """Get all players from today's games.
    
    Returns:
        Dict mapping player_id to player info (name, team, etc.)
    """
    players = {}
    team_ids = set()
    
    # Collect all team IDs from games
    for game in games:
        team_ids.add(game['team_id'])
        team_ids.add(game['opponent_team_id'])
    
    season = season[:-3]
    # Get rosters for all teams
    for team_id in team_ids:
        # roster season is 2025 not 2025-26 so shave off the -26

        roster = RosterORM.get_by_team_and_season(team_id, season, db=db)
        team = TeamORM.get_by_id(team_id, db=db)
        team_name = team.name if team else f"Team {team_id}"
        
        for entry in roster:
            if entry.player_id not in players:
                players[entry.player_id] = {
                    'player_id': entry.player_id,
                    'player_name': entry.player_name,
                    'team_id': team_id,
                    'team_name': team_name,
                    'position': entry.position,
                    'number': entry.player_number
                }
    
    return players


def format_streak_row(streak):
    """Format a streak row for display."""
    active_indicator = "🔥 ACTIVE" if streak.is_active else "✓ Complete"
    kind_display = "Current" if streak.streak_kind == 'current' else "Season Best"
    
    return (
        f"{streak.player_name:<25} | "
        f"{streak.stat:>4} | "
        f">={streak.threshold:>3} | "
        f"{streak.streak_games:>3} games | "
        f"{streak.start_date.strftime('%m/%d')} - {streak.end_date.strftime('%m/%d')} | "
        f"{kind_display:>12} | "
        f"{active_indicator}"
    )


def get_heat_status_from_zscore(z_score: float) -> tuple:
    """Get heat status from z-score with refined categorization.
    
    Returns:
        Tuple of (status_text, emoji)
    """
    if z_score >= 1.0:
        return ("ON FIRE", "🔥")
    elif z_score >= 0.65:
        return ("HEATING UP", "📈")
    elif z_score >= -0.64:
        return ("AVERAGE", "➖")
    elif z_score >= -1.0:
        return ("COOLING OFF", "📉")
    else:
        return ("ICE COLD", "🧊")


def format_heat_row(heat):
    """Format a heat index row for display."""
    # Use z-score directly for status (more accurate than stored status)
    status_text, status_emoji = get_heat_status_from_zscore(heat.z_score)
    
    return (
        f"{heat.player_name:<25} | "
        f"{heat.stat:>4} | "
        f"{heat.window_size:>2}g | "
        f"Z: {heat.z_score:>6.2f} | "
        f"Recent: {heat.recent_avg:>6.2f} | "
        f"Season: {heat.season_avg:>6.2f} | "
        f"{status_emoji} {status_text}"
    )


def format_window_row(window):
    """Format a stat window row for display."""
    hit_rate = (window.games_hit / window.games_played * 100) if window.games_played > 0 else 0
    hit_rate_str = f"{hit_rate:.1f}%"
    
    if hit_rate >= 80:
        indicator = "🔥"
    elif hit_rate >= 60:
        indicator = "✓"
    elif hit_rate >= 40:
        indicator = "○"
    else:
        indicator = "✗"
    
    return (
        f"{window.player_name:<25} | "
        f"{window.stat:>4} | "
        f">={window.threshold:>3} | "
        f"{window.games_hit:>2}/{window.games_played:>2} | "
        f"{window.window_size:>2}g | "
        f"{hit_rate_str:>6} | "
        f"{window.last_game_date.strftime('%m/%d/%Y')} | "
        f"{indicator}"
    )


def get_player_season_averages(heat_indices: List, player_id: int) -> Dict[str, float]:
    """Get player's season averages from heat index data.
    
    Args:
        heat_indices: List of all heat index records
        player_id: Player ID
    
    Returns:
        Dict mapping stat -> season average
    """
    averages = {}
    for heat in heat_indices:
        if heat.player_id == player_id and heat.stat not in averages:
            averages[heat.stat] = heat.season_avg
    return averages


def score_streak(streak, player_avg: float = None) -> float:
    """Score a streak for sorting - higher is better.
    
    Uses threshold relative to player average if available, otherwise absolute threshold.
    Prioritizes: active streaks, higher relative thresholds, longer streaks.
    
    Args:
        streak: Streak object
        player_avg: Player's season average for this stat (optional)
    
    Returns:
        Score for sorting
    """
    # Base score from threshold
    if player_avg and player_avg > 0:
        # Relative threshold (as % of average) - more meaningful
        relative_thresh = streak.threshold / player_avg
        threshold_score = relative_thresh * 100
    else:
        # Absolute threshold fallback
        threshold_score = streak.threshold
    
    # Boost for active streaks
    active_boost = 1000 if streak.is_active else 0
    
    # Boost for current streaks (vs season best)
    kind_boost = 100 if streak.streak_kind == 'current' else 0
    
    return active_boost + kind_boost + threshold_score + (streak.streak_games * 0.1)


def format_consistency_row(cons: PlayerConsistencyORM) -> str:
    """Format a consistency row for display."""
    tier_emoji = {
        'steady': '🎯',
        'average': '➖',
        'volatile': '🎰'
    }
    emoji = tier_emoji.get(cons.consistency_tier, '❓')
    
    return (
        f"{cons.stat_name.upper():>4} | "
        f"Avg: {cons.mean:>6.1f} | "
        f"StdDev: {cons.stddev:>5.1f} | "
        f"CV: {cons.cv:>5.2f} | "
        f"Range: {cons.min_val:.0f}-{cons.max_val:.0f} | "
        f"{emoji} {cons.consistency_tier.upper()}"
    )


def get_consistency_summary(consistency_records: List[PlayerConsistencyORM]) -> Dict[str, str]:
    """Get a summary of player's consistency profile.
    
    Args:
        consistency_records: List of consistency records for a player
        
    Returns:
        Dict with 'overall' classification and 'stats' breakdown
    """
    if not consistency_records:
        return {'overall': 'unknown', 'steady_count': 0, 'volatile_count': 0}
    
    steady_count = sum(1 for c in consistency_records if c.consistency_tier == 'steady')
    volatile_count = sum(1 for c in consistency_records if c.consistency_tier == 'volatile')
    
    if steady_count > volatile_count + 2:
        overall = 'steady'
    elif volatile_count > steady_count + 2:
        overall = 'volatile'
    else:
        overall = 'mixed'
    
    return {
        'overall': overall,
        'steady_count': steady_count,
        'volatile_count': volatile_count
    }


def score_window(window, player_avg: float = None) -> float:
    """Score a stat window for sorting - balances threshold and hit rate.
    
    Prioritizes windows with meaningful hit rates. High thresholds with 0% hit rate
    are not useful, so we filter them out or heavily penalize them.
    
    Args:
        window: Window object
        player_avg: Player's season average for this stat (optional)
    
    Returns:
        Score for sorting (higher is better), or -1 to filter out
    """
    hit_rate = (window.games_hit / window.games_played) if window.games_played > 0 else 0
    
    # Aggressively filter out 0% hit rate windows - they're not useful
    if hit_rate == 0:
        return -1  # Filter out completely
    
    # For very low hit rates (< 20%), only keep if threshold is reasonable relative to player
    if hit_rate < 0.2:
        if player_avg and player_avg > 0:
            # Only keep if threshold is close to player average (not way above)
            if window.threshold > player_avg * 1.5:
                return -1  # Too high threshold for such low hit rate
        else:
            # No player avg, filter out low hit rates
            return -1
    
    # Base score from threshold (relative to player average if available)
    if player_avg and player_avg > 0:
        relative_thresh = window.threshold / player_avg
        # Higher relative thresholds get more points, but cap it
        threshold_score = min(relative_thresh * 50, 100)  # Max 100 points for threshold
    else:
        # Absolute threshold scoring - higher thresholds get more points
        threshold_score = min(window.threshold * 3, 100)  # PRA 30 = 90, PTS 25 = 75, AST 6 = 18
    
    # Hit rate score (0-50 points) - important but threshold matters more
    hit_rate_score = hit_rate * 50
    
    # Window size bonus - 10g windows are more meaningful than 5g
    window_bonus = 10 if window.window_size == 10 else 0
    
    # Combined score: threshold (weighted more) + hit rate + window bonus
    return threshold_score + hit_rate_score + window_bonus


def sort_streaks_by_player(streaks: List, heat_indices: List) -> Dict[int, List]:
    """Sort streaks per player using player-specific scoring.
    
    Args:
        streaks: List of all streaks
        heat_indices: List of all heat indices (for season averages)
    
    Returns:
        Dict mapping player_id -> sorted list of streaks
    """
    streaks_by_player = defaultdict(list)
    for streak in streaks:
        streaks_by_player[streak.player_id].append(streak)
    
    # Sort each player's streaks
    for player_id, player_streaks in streaks_by_player.items():
        player_avgs = get_player_season_averages(heat_indices, player_id)
        
        # Sort with player-specific scoring
        player_streaks.sort(
            key=lambda s: score_streak(s, player_avgs.get(s.stat)),
            reverse=True
        )
    
    return streaks_by_player


def sort_windows_by_player(windows: List, heat_indices: List) -> Dict[int, List]:
    """Sort stat windows per player using player-specific scoring.
    
    Args:
        windows: List of all windows
        heat_indices: List of all heat indices (for season averages)
    
    Returns:
        Dict mapping player_id -> sorted list of windows
    """
    windows_by_player = defaultdict(list)
    for window in windows:
        windows_by_player[window.player_id].append(window)
    
    # Sort each player's windows
    for player_id, player_windows in windows_by_player.items():
        player_avgs = get_player_season_averages(heat_indices, player_id)
        
        # Score and filter
        scored_windows = []
        for window in player_windows:
            score = score_window(window, player_avgs.get(window.stat))
            if score >= 0:  # Only include windows that pass minimum criteria
                scored_windows.append((score, window))
        
        # Sort by score (descending)
        scored_windows.sort(key=lambda x: x[0], reverse=True)
        
        # Extract windows
        windows_by_player[player_id] = [w for _, w in scored_windows]
    
    return windows_by_player


def generate_report(target_date: date, season: str, output_file: str):
    """Generate comprehensive report for today's games."""
    lines = []
    
    with get_db_context() as db:
        # Get today's games
        games = GameScheduleORM.get_by_date(target_date, db=db)
        
        if not games:
            lines.append("=" * 120)
            lines.append(f"NO GAMES SCHEDULED FOR {target_date.strftime('%Y-%m-%d')}")
            lines.append("=" * 120)
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))
                print(f"Report saved to {output_file}")
            elif target_date == date.today():
                print("\n".join(lines))
            return
        
        # Get all players from today's games
        players = get_players_from_games(games, season, db=db)
        player_ids = list(players.keys())
        
        if not player_ids:
            lines.append("=" * 120)
            lines.append(f"NO PLAYERS FOUND FOR GAMES ON {target_date.strftime('%Y-%m-%d')}")
            lines.append("=" * 120)
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write("\n".join(lines))
                print(f"Report saved to {output_file}")
            else:
                print("\n".join(lines))
            return
        
        # Header
        lines.append("=" * 120)
        lines.append(f"TODAY'S GAMES REPORT - {target_date.strftime('%A, %B %d, %Y')}")
        lines.append(f"Season: {season} | {len(games)} Game(s) | {len(player_ids)} Players")
        lines.append("=" * 120)
        lines.append("")
        
        # Games Overview
        lines.append("📅 GAMES SCHEDULED")
        lines.append("-" * 120)
        for game in games:
            game_time = game.get('game_date', 'TBD')
            if isinstance(game_time, datetime):
                game_time = game_time.strftime('%I:%M %p')
            lines.append(
                f"{game.get('team_name', 'Team')} vs {game.get('opponent_name', 'Opponent')} "
                f"({game.get('team_abbreviation', '')} vs {game.get('opponent_abbreviation', '')}) "
                f"at {game_time}"
            )
        lines.append("")
        lines.append("")
        
        anchor = load_latest_complete_snapshot(
            db,
            PlayerStatWindowSnapshotORM,
            season=season,
            requested_cutoff=feature_cutoff_for_slate(target_date),
            player_ids=player_ids,
        )
        if anchor.feature_as_of is not None:
            streaks = [
                row for row in load_complete_snapshot_at_cutoff(
                    db,
                    PlayerConsecutiveStreakSnapshotORM,
                    season=season,
                    feature_as_of=anchor.feature_as_of,
                    player_ids=player_ids,
                ).rows
                if row.streak_games >= 3
            ]
            heat_indices = list(load_complete_snapshot_at_cutoff(
                db,
                PlayerHeatIndexSnapshotORM,
                season=season,
                feature_as_of=anchor.feature_as_of,
                player_ids=player_ids,
            ).rows)
            stat_windows = list(anchor.rows)
            consistency_data = [
                row for row in load_complete_snapshot_at_cutoff(
                    db,
                    PlayerConsistencySnapshotORM,
                    season=season,
                    feature_as_of=anchor.feature_as_of,
                    player_ids=player_ids,
                ).rows
                if row.window_size == 0
            ]
            heat_indices.sort(key=lambda row: row.z_score, reverse=True)
            lines.append(
                "Player analytics snapshot: "
                f"{anchor.feature_as_of.isoformat()} ({anchor.calculation_version}, complete)"
            )
            lines.append("")
        else:
            if complete_snapshot_history_exists(db, season=season):
                streaks = heat_indices = stat_windows = consistency_data = []
                lines.append(
                    "Player analytics snapshot: missing at requested cutoff "
                    "(legacy fallback suppressed to prevent future leakage)"
                )
            elif target_date == date.today():
                # Expand/migrate compatibility: legacy tables remain readable
                # only until this season has any v2 history.
                streaks = db.query(ConsecutiveStreakORM).filter(
                    ConsecutiveStreakORM.player_id.in_(player_ids),
                    ConsecutiveStreakORM.season == season,
                    ConsecutiveStreakORM.streak_games >= 3
                ).all()
                heat_indices = db.query(PlayerHeatIndexORM).filter(
                    PlayerHeatIndexORM.player_id.in_(player_ids),
                    PlayerHeatIndexORM.season == season
                ).order_by(PlayerHeatIndexORM.z_score.desc()).all()
                stat_windows = db.query(PlayerStatWindowORM).filter(
                    PlayerStatWindowORM.player_id.in_(player_ids),
                    PlayerStatWindowORM.season == season
                ).all()
                consistency_data = db.query(PlayerConsistencyORM).filter(
                    PlayerConsistencyORM.player_id.in_(player_ids),
                    PlayerConsistencyORM.season == season,
                    PlayerConsistencyORM.window_size == 0
                ).all()
                lines.append("Player analytics snapshot: legacy latest-state fallback (unversioned)")
            else:
                streaks = heat_indices = stat_windows = consistency_data = []
                lines.append(
                    "Player analytics snapshot: missing at requested cutoff "
                    "(historical legacy fallback suppressed)"
                )
            lines.append("")
        
        # Group consistency by player
        consistency_by_player = defaultdict(list)
        for cons in consistency_data:
            consistency_by_player[cons.player_id].append(cons)
        
        # Group and sort by player using player-specific scoring
        streaks_by_player = sort_streaks_by_player(streaks, heat_indices)
        windows_by_player = sort_windows_by_player(stat_windows, heat_indices)
        
        # Group heat indices by player
        heat_by_player = defaultdict(list)
        for heat in heat_indices:
            heat_by_player[heat.player_id].append(heat)
        
        # Per-Player Detailed Sections
        lines.append("=" * 120)
        lines.append("PLAYER-BY-PLAYER BREAKDOWN")
        lines.append("=" * 120)
        lines.append("")
        
        # Sort players by team, then by name
        sorted_players = sorted(players.values(), key=lambda p: (p['team_name'], p['player_name']))
        
        for player_info in sorted_players:
            player_id = player_info['player_id']
            player_name = player_info['player_name']
            team_name = player_info['team_name']
            position = player_info.get('position', 'N/A')
            number = player_info.get('number', 'N/A')
            
            lines.append("-" * 120)
            lines.append(f"👤 {player_name} ({team_name}) - #{number} {position}")
            lines.append("-" * 120)
            
            # Streaks - already filtered and sorted by threshold
            player_streaks = streaks_by_player.get(player_id, [])
            if player_streaks:
                lines.append("  🔥 CONSECUTIVE STREAKS:")
                lines.append("  " + "-" * 116)
                lines.append("  " + f"{'Stat':<4} | {'Thresh':>7} | {'Length':>8} | {'Date Range':>15} | {'Kind':>12} | {'Status':>10}")
                lines.append("  " + "-" * 116)
                for streak in player_streaks[:10]:  # Top 10 streaks (sorted by player-specific scoring)
                    # Remove player name from formatted row since it's already in header
                    row = format_streak_row(streak)
                    parts = row.split(" | ", 1)
                    if len(parts) > 1:
                        lines.append("  " + parts[1])
                    else:
                        lines.append("  " + row)
            else:
                lines.append("  🔥 CONSECUTIVE STREAKS: None")
            
            lines.append("")
            
            # Heat Index - sort by z-score (most on fire first)
            player_heat = heat_by_player.get(player_id, [])
            if player_heat:
                # Sort by z-score descending
                player_heat_sorted = sorted(player_heat, key=lambda h: h.z_score, reverse=True)
                lines.append("  🌡️  HEAT INDEX:")
                lines.append("  " + "-" * 116)
                lines.append("  " + f"{'Stat':<4} | {'Win':>4} | {'Z-Score':>8} | {'Recent':>8} | {'Season':>8} | {'Status':>15}")
                lines.append("  " + "-" * 116)
                for heat in player_heat_sorted[:10]:  # Top 10 heat indices by z-score
                    # Remove player name from formatted row since it's already in header
                    row = format_heat_row(heat)
                    parts = row.split(" | ", 1)
                    if len(parts) > 1:
                        lines.append("  " + parts[1])
                    else:
                        lines.append("  " + row)
            else:
                lines.append("  🌡️  HEAT INDEX: None")
            
            lines.append("")
            
            # Stat Windows - already filtered and sorted by threshold
            player_windows = windows_by_player.get(player_id, [])
            if player_windows:
                lines.append("  📊 STAT WINDOWS (Recent Form):")
                lines.append("  " + "-" * 116)
                lines.append("  " + f"{'Stat':<4} | {'Thresh':>7} | {'Hit':>6} | {'Win':>4} | {'Rate':>6} | {'Last Game':>12} | {'Status'}")
                lines.append("  " + "-" * 116)
                for window in player_windows[:10]:  # Top 10 windows (sorted by threshold + hit rate score)
                    # Remove player name from formatted row since it's already in header
                    row = format_window_row(window)
                    parts = row.split(" | ", 1)
                    if len(parts) > 1:
                        lines.append("  " + parts[1])
                    else:
                        lines.append("  " + row)
            else:
                lines.append("  📊 STAT WINDOWS: None")
            
            lines.append("")
            
            # Consistency Profile
            player_consistency = consistency_by_player.get(player_id, [])
            if player_consistency:
                summary = get_consistency_summary(player_consistency)
                overall_emoji = {'steady': '🎯', 'volatile': '🎰', 'mixed': '↔️'}.get(summary['overall'], '❓')
                
                lines.append(f"  📈 CONSISTENCY PROFILE ({overall_emoji} {summary['overall'].upper()}):")
                lines.append("  " + "-" * 116)
                lines.append("  " + f"{'Stat':>4} | {'Avg':>8} | {'StdDev':>8} | {'CV':>6} | {'Range':>12} | {'Tier':>15}")
                lines.append("  " + "-" * 116)
                
                # Sort by stat importance (PTS, REB, AST, PRA first)
                stat_order = {'pts': 0, 'reb': 1, 'ast': 2, 'pra': 3, 'stl': 4, 'blk': 5, 'tov': 6}
                sorted_cons = sorted(player_consistency, key=lambda c: stat_order.get(c.stat_name, 99))
                
                for cons in sorted_cons:
                    lines.append("  " + format_consistency_row(cons))
            else:
                lines.append("  📈 CONSISTENCY PROFILE: No data")
            
            lines.append("")
        
        # Summary Sections
        lines.append("")
        lines.append("=" * 120)
        lines.append("SUMMARY: ACTIVE STREAKS (All Players)")
        lines.append("=" * 120)
        lines.append("")
        
        active_streaks = [s for s in streaks if s.is_active and s.streak_kind == 'current']
        if active_streaks:
            # Sort active streaks by player-specific scoring for summary
            player_avgs_dict = {}
            for heat in heat_indices:
                if heat.player_id not in player_avgs_dict:
                    player_avgs_dict[heat.player_id] = {}
                if heat.stat not in player_avgs_dict[heat.player_id]:
                    player_avgs_dict[heat.player_id][heat.stat] = heat.season_avg
            
            active_streaks_sorted = sorted(
                active_streaks,
                key=lambda s: score_streak(s, player_avgs_dict.get(s.player_id, {}).get(s.stat)),
                reverse=True
            )
            
            lines.append(f"🔥 {len(active_streaks)} Active Current Streaks")
            lines.append("-" * 120)
            lines.append(f"{'Player':<25} | {'Stat':>4} | {'Thresh':>7} | {'Length':>8} | {'Date Range':>15} | {'Status':>10}")
            lines.append("-" * 120)
            for streak in active_streaks_sorted[:30]:
                lines.append(format_streak_row(streak))
        else:
            lines.append("No active streaks found")
        
        lines.append("")
        lines.append("")
        
        # Season Best Streaks (non-active but high threshold and/or long length)
        season_best_streaks = [s for s in streaks if s.streak_kind == 'season_max' and not s.is_active]
        if season_best_streaks:
            # Filter to meaningful streaks: either long (5+ games) or high threshold relative to player
            player_avgs_dict = {}
            for heat in heat_indices:
                if heat.player_id not in player_avgs_dict:
                    player_avgs_dict[heat.player_id] = {}
                if heat.stat not in player_avgs_dict[heat.player_id]:
                    player_avgs_dict[heat.player_id][heat.stat] = heat.season_avg
            
            # Filter season best streaks
            meaningful_season_best = []
            for streak in season_best_streaks:
                player_avg = player_avgs_dict.get(streak.player_id, {}).get(streak.stat)
                
                # Keep if: 5+ games OR threshold is high relative to player average
                if streak.streak_games >= 5:
                    meaningful_season_best.append(streak)
                elif player_avg and player_avg > 0:
                    # Threshold should be at least 80% of player average (meaningful)
                    if streak.threshold >= player_avg * 0.8:
                        meaningful_season_best.append(streak)
                else:
                    # No player avg, use absolute thresholds
                    min_thresholds = {'PTS': 20, 'REB': 8, 'AST': 5, 'STL': 2, 'BLK': 2, 'FG3M': 3, 'PRA': 25}
                    if streak.threshold >= min_thresholds.get(streak.stat, 5):
                        meaningful_season_best.append(streak)
            
            if meaningful_season_best:
                season_best_sorted = sorted(
                    meaningful_season_best,
                    key=lambda s: (
                        s.streak_games,  # Length first
                        score_streak(s, player_avgs_dict.get(s.player_id, {}).get(s.stat))  # Then score
                    ),
                    reverse=True
                )
                
                lines.append("=" * 120)
                lines.append("SUMMARY: SEASON BEST STREAKS (5+ Games OR High Threshold)")
                lines.append("=" * 120)
                lines.append("")
                lines.append(f"⭐ {len(meaningful_season_best)} Season Best Streaks (Filtered)")
                lines.append("-" * 120)
                lines.append(f"{'Player':<25} | {'Stat':>4} | {'Thresh':>7} | {'Length':>8} | {'Date Range':>15} | {'Status':>10}")
                lines.append("-" * 120)
                for streak in season_best_sorted[:30]:
                    lines.append(format_streak_row(streak))
        
        lines.append("")
        lines.append("")
        
        lines.append("=" * 120)
        lines.append("SUMMARY: ON FIRE / ICE COLD (All Players)")
        lines.append("=" * 120)
        lines.append("")
        
        # Categorize by refined z-score thresholds
        on_fire = [h for h in heat_indices if h.z_score >= 1.0]
        heating_up = [h for h in heat_indices if 0.65 <= h.z_score < 1.0]
        average = [h for h in heat_indices if -0.64 <= h.z_score < 0.65]
        cooling_off = [h for h in heat_indices if -1.0 <= h.z_score < -0.64]
        ice_cold = [h for h in heat_indices if h.z_score < -1.0]
        
        if on_fire:
            lines.append(f"🔥 {len(on_fire)} Players ON FIRE (Z ≥ 1.0)")
            lines.append("-" * 120)
            lines.append(f"{'Player':<25} | {'Stat':>4} | {'Win':>4} | {'Z-Score':>8} | {'Recent':>8} | {'Season':>8} | {'Status':>12}")
            lines.append("-" * 120)
            for heat in sorted(on_fire, key=lambda h: h.z_score, reverse=True)[:20]:
                lines.append(format_heat_row(heat))
        
        lines.append("")
        
        if heating_up:
            lines.append(f"📈 {len(heating_up)} Players HEATING UP (0.65 ≤ Z < 1.0)")
            lines.append("-" * 120)
            lines.append(f"{'Player':<25} | {'Stat':>4} | {'Win':>4} | {'Z-Score':>8} | {'Recent':>8} | {'Season':>8} | {'Status':>12}")
            lines.append("-" * 120)
            for heat in sorted(heating_up, key=lambda h: h.z_score, reverse=True)[:15]:
                lines.append(format_heat_row(heat))
        
        lines.append("")
        
        if cooling_off:
            lines.append(f"📉 {len(cooling_off)} Players COOLING OFF (-1.0 ≤ Z < -0.65)")
            lines.append("-" * 120)
            lines.append(f"{'Player':<25} | {'Stat':>4} | {'Win':>4} | {'Z-Score':>8} | {'Recent':>8} | {'Season':>8} | {'Status':>12}")
            lines.append("-" * 120)
            for heat in sorted(cooling_off, key=lambda h: h.z_score)[:15]:
                lines.append(format_heat_row(heat))
        
        lines.append("")
        
        if ice_cold:
            lines.append(f"🧊 {len(ice_cold)} Players ICE COLD (Z < -1.0)")
            lines.append("-" * 120)
            lines.append(f"{'Player':<25} | {'Stat':>4} | {'Win':>4} | {'Z-Score':>8} | {'Recent':>8} | {'Season':>8} | {'Status':>12}")
            lines.append("-" * 120)
            for heat in sorted(ice_cold, key=lambda h: h.z_score)[:20]:
                lines.append(format_heat_row(heat))
        
        lines.append("")
        lines.append("")
        
        lines.append("=" * 120)
        lines.append("SUMMARY: TOP STAT WINDOWS (All Players)")
        lines.append("=" * 120)
        lines.append("")
        
        if stat_windows:
            # Score all windows for summary (combining threshold and hit rate)
            # Filter out 0% and very low hit rate windows
            player_avgs_dict = {}
            for heat in heat_indices:
                if heat.player_id not in player_avgs_dict:
                    player_avgs_dict[heat.player_id] = {}
                if heat.stat not in player_avgs_dict[heat.player_id]:
                    player_avgs_dict[heat.player_id][heat.stat] = heat.season_avg
            
            # Separate 10g and 5g windows
            windows_10g = []
            windows_5g = []
            
            for window in stat_windows:
                hit_rate = (window.games_hit / window.games_played) if window.games_played > 0 else 0
                # Only include windows with at least 20% hit rate
                if hit_rate >= 0.2:
                    score = score_window(window, player_avgs_dict.get(window.player_id, {}).get(window.stat))
                    if score >= 0:
                        if window.window_size == 10:
                            windows_10g.append((score, window))
                        else:
                            windows_5g.append((score, window))
            
            windows_10g.sort(key=lambda x: x[0], reverse=True)
            windows_5g.sort(key=lambda x: x[0], reverse=True)
            
            if windows_10g or windows_5g:
                # 10-game windows section
                if windows_10g:
                    lines.append(f"📊 Top {min(30, len(windows_10g))} Stat Windows - 10 Game Window (Min 20% Hit Rate)")
                    lines.append("-" * 120)
                    lines.append(f"{'Player':<25} | {'Stat':>4} | {'Thresh':>7} | {'Hit':>6} | {'Win':>4} | {'Rate':>6} | {'Last Game':>12} | {'Status'}")
                    lines.append("-" * 120)
                    for _, window in windows_10g[:30]:
                        lines.append(format_window_row(window))
                    lines.append("")
                
                # 5-game windows section
                if windows_5g:
                    lines.append(f"📊 Top {min(30, len(windows_5g))} Stat Windows - 5 Game Window (Min 20% Hit Rate)")
                    lines.append("-" * 120)
                    lines.append(f"{'Player':<25} | {'Stat':>4} | {'Thresh':>7} | {'Hit':>6} | {'Win':>4} | {'Rate':>6} | {'Last Game':>12} | {'Status'}")
                    lines.append("-" * 120)
                    for _, window in windows_5g[:30]:
                        lines.append(format_window_row(window))
            else:
                lines.append("No stat windows found with meaningful hit rates (≥20%)")
        else:
            lines.append("No stat windows found")
        
        lines.append("")
        
        # Consistency Summary Section
        if consistency_data:
            lines.append("=" * 120)
            lines.append("SUMMARY: PLAYER CONSISTENCY PROFILES")
            lines.append("=" * 120)
            lines.append("")
            
            # Most volatile players (highest CV across key stats)
            volatile_players = []
            steady_players = []
            
            for player_id, cons_list in consistency_by_player.items():
                player_info = players.get(player_id, {})
                player_name = player_info.get('player_name', f'Player {player_id}')
                team_name = player_info.get('team_name', '')
                
                # Get PTS consistency as primary indicator
                pts_cons = next((c for c in cons_list if c.stat_name == 'pts'), None)
                pra_cons = next((c for c in cons_list if c.stat_name == 'pra'), None)
                
                if pts_cons:
                    volatile_players.append({
                        'name': player_name,
                        'team': team_name,
                        'stat': 'PTS',
                        'cv': pts_cons.cv,
                        'mean': pts_cons.mean,
                        'stddev': pts_cons.stddev,
                        'tier': pts_cons.consistency_tier
                    })
                elif pra_cons:
                    volatile_players.append({
                        'name': player_name,
                        'team': team_name,
                        'stat': 'PRA',
                        'cv': pra_cons.cv,
                        'mean': pra_cons.mean,
                        'stddev': pra_cons.stddev,
                        'tier': pra_cons.consistency_tier
                    })
            
            # Sort by CV
            volatile_sorted = sorted(volatile_players, key=lambda x: x['cv'], reverse=True)
            steady_sorted = sorted(volatile_players, key=lambda x: x['cv'])
            
            # Most Volatile
            lines.append("🎰 MOST VOLATILE PLAYERS (Highest CV - Boom/Bust)")
            lines.append("-" * 120)
            lines.append(f"{'Player':<28} | {'Team':<20} | {'Stat':>4} | {'Avg':>6} | {'StdDev':>6} | {'CV':>5} | {'Tier':>10}")
            lines.append("-" * 120)
            for p in volatile_sorted[:15]:
                tier_emoji = '🎰' if p['tier'] == 'volatile' else '➖' if p['tier'] == 'average' else '🎯'
                lines.append(
                    f"{p['name']:<28} | {p['team']:<20} | {p['stat']:>4} | "
                    f"{p['mean']:>6.1f} | {p['stddev']:>6.1f} | {p['cv']:>5.2f} | {tier_emoji} {p['tier']}"
                )
            lines.append("")
            
            # Most Steady
            lines.append("🎯 MOST STEADY PLAYERS (Lowest CV - Reliable)")
            lines.append("-" * 120)
            lines.append(f"{'Player':<28} | {'Team':<20} | {'Stat':>4} | {'Avg':>6} | {'StdDev':>6} | {'CV':>5} | {'Tier':>10}")
            lines.append("-" * 120)
            for p in steady_sorted[:15]:
                tier_emoji = '🎯' if p['tier'] == 'steady' else '➖' if p['tier'] == 'average' else '🎰'
                lines.append(
                    f"{p['name']:<28} | {p['team']:<20} | {p['stat']:>4} | "
                    f"{p['mean']:>6.1f} | {p['stddev']:>6.1f} | {p['cv']:>5.2f} | {tier_emoji} {p['tier']}"
                )
            lines.append("")
        
        lines.append("")
        lines.append("=" * 120)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 120)
    
    # Output
    output = "\n".join(lines)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ Report saved to {output_file}")
        print(f"   {len(games)} game(s), {len(player_ids)} players")
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(description='Generate report for today\'s games')
    parser.add_argument('--date', type=str, help='Date (YYYY-MM-DD)', default=None)
    parser.add_argument('--output', type=str, help='Output file path', 
                       default=f"todays_games_report_{datetime.now().strftime('%Y%m%d')}.txt")
    parser.add_argument('--season', type=str, help='Season (e.g., 2024-25)', default=None)
    
    args = parser.parse_args()
    
    # Determine date
    if args.date:
        target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        target_date = date.today()
    
    # Determine season
    season = args.season or get_current_season()
    
    # Generate report
    generate_report(target_date, season, args.output)


if __name__ == "__main__":
    main()
