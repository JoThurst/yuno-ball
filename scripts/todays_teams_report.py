"""
Script to generate a comprehensive team analytics report.

This script creates a text file with team metrics, flags, game environments,
schedule factors (B2B, rest edges), and strength of schedule for all teams,
with special focus on today's games.

Usage:
    python todays_teams_report.py                    # Generate report for today
    python todays_teams_report.py --output report.txt # Custom output file
    python todays_teams_report.py --date 2025-12-01  # Specific date
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Add project root to Python path
# Go up one level from scripts/ to project root
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from app.database import get_db_context
from app.models.team_sqlalchemy import TeamORM
from app.models.team_daily_metrics_sqlalchemy import TeamDailyMetricsORM
from app.models.team_daily_flags_sqlalchemy import TeamDailyFlagsORM
from app.models.game_environment_daily_sqlalchemy import GameEnvironmentDailyORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_schedule_factors_sqlalchemy import TeamScheduleFactorsORM
from app.models.game_odds_sqlalchemy import GameOddsORM


def get_current_season():
    """Get current season string."""
    now = datetime.now()
    if now.month > 9:  # October onwards
        return f"{now.year}-{str(now.year + 1)[-2:]}"
    else:
        return f"{now.year - 1}-{str(now.year)[-2:]}"


# =============================================================================
# SCHEDULE FACTORS FORMATTING UTILITIES
# =============================================================================

def format_rest_days(days_rest: Optional[int]) -> str:
    """Format days of rest with emoji indicator.
    
    Args:
        days_rest: Number of days since last game (0 = B2B)
        
    Returns:
        Formatted string with rest emoji
    """
    if days_rest is None:
        return "N/A"
    
    if days_rest == 0:
        return "🔴 B2B (0 days)"
    elif days_rest == 1:
        return "🟡 1 day rest"
    elif days_rest == 2:
        return "🟢 2 days rest"
    elif days_rest >= 3:
        return f"💚 {days_rest} days rest"
    else:
        return f"{days_rest} days rest"


def format_rest_edge(rest_edge: Optional[str], rest_diff: Optional[int]) -> str:
    """Format rest edge with emoji and description.
    
    Args:
        rest_edge: 'advantage' | 'even' | 'disadvantage'
        rest_diff: days_rest - opponent_days_rest
        
    Returns:
        Formatted string with edge indicator
    """
    if rest_edge is None or rest_diff is None:
        return "N/A"
    
    if rest_edge == 'advantage':
        return f"✅ Advantage (+{rest_diff} days)"
    elif rest_edge == 'disadvantage':
        return f"❌ Disadvantage ({rest_diff} days)"
    else:
        return f"➖ Even ({rest_diff:+d})"


def format_schedule_flags(factors: TeamScheduleFactorsORM) -> List[str]:
    """Get list of schedule flags for a team.
    
    Args:
        factors: TeamScheduleFactorsORM record
        
    Returns:
        List of flag strings
    """
    flags = []
    
    if factors.is_b2b:
        flags.append("🔴 B2B")
    if factors.is_3_in_4:
        flags.append("🟠 3-in-4")
    if factors.is_4_in_5:
        flags.append("🟡 4-in-5")
    if factors.is_5_in_7:
        flags.append("⚠️ 5-in-7")
    
    return flags


def format_schedule_factors_short(factors: TeamScheduleFactorsORM) -> str:
    """Format schedule factors as a short one-line summary.
    
    Args:
        factors: TeamScheduleFactorsORM record
        
    Returns:
        Short formatted string
    """
    parts = []
    
    # Rest days
    if factors.days_rest is not None:
        if factors.is_b2b:
            parts.append("🔴 B2B")
        else:
            parts.append(f"{factors.days_rest}d rest")
    
    # Schedule flags
    schedule_flags = []
    if factors.is_3_in_4:
        schedule_flags.append("3in4")
    if factors.is_4_in_5:
        schedule_flags.append("4in5")
    if factors.is_5_in_7:
        schedule_flags.append("5in7")
    
    if schedule_flags:
        parts.append(f"({', '.join(schedule_flags)})")
    
    # Rest edge
    if factors.rest_edge == 'advantage':
        parts.append(f"✅ +{factors.rest_diff}d edge")
    elif factors.rest_edge == 'disadvantage':
        parts.append(f"❌ {factors.rest_diff}d edge")
    
    return " | ".join(parts) if parts else "No schedule data"


def format_schedule_factors_detail(factors: TeamScheduleFactorsORM, team_name: str) -> List[str]:
    """Format detailed schedule factors for a team.
    
    Args:
        factors: TeamScheduleFactorsORM record
        team_name: Name of the team
        
    Returns:
        List of formatted lines
    """
    lines = []
    
    lines.append(f"  Schedule Situation:")
    lines.append(f"    Rest: {format_rest_days(factors.days_rest)}")
    
    # Schedule flags
    sched_flags = format_schedule_flags(factors)
    if sched_flags:
        lines.append(f"    Flags: {', '.join(sched_flags)}")
    
    # Games in windows
    if factors.games_last_4 is not None:
        lines.append(f"    Games: {factors.games_last_4} in last 4 days, {factors.games_last_7} in last 7 days")
    
    # Rest edge
    lines.append(f"    vs Opponent: {format_rest_edge(factors.rest_edge, factors.rest_diff)}")
    if factors.opponent_days_rest is not None:
        lines.append(f"    Opponent Rest: {factors.opponent_days_rest} days")
    
    return lines


# =============================================================================
# STRENGTH OF SCHEDULE FORMATTING UTILITIES
# =============================================================================

def format_sos_metric(season_val: Optional[float], last10_val: Optional[float], 
                      delta_val: Optional[float] = None) -> str:
    """Format a strength of schedule metric.
    
    Args:
        season_val: Season SoS value
        last10_val: Last 10 games SoS value
        delta_val: Optional delta (computed if not provided)
        
    Returns:
        Formatted string with trend indicator
    """
    if season_val is None and last10_val is None:
        return "N/A"
    
    if delta_val is None and season_val is not None and last10_val is not None:
        delta_val = last10_val - season_val
    
    parts = []
    
    if season_val is not None:
        parts.append(f"Season: {season_val:+.1f}")
    
    if last10_val is not None:
        parts.append(f"L10: {last10_val:+.1f}")
    
    if delta_val is not None:
        # Positive delta = harder recent schedule
        if delta_val > 1.5:
            emoji = "📈"  # Schedule got harder
            interpretation = "harder"
        elif delta_val < -1.5:
            emoji = "📉"  # Schedule got easier
            interpretation = "easier"
        else:
            emoji = "➖"
            interpretation = "similar"
        parts.append(f"({delta_val:+.1f} {emoji} {interpretation})")
    
    return " | ".join(parts)


def format_sos_summary(metrics: TeamDailyMetricsORM) -> List[str]:
    """Format strength of schedule summary for a team.
    
    Args:
        metrics: TeamDailyMetricsORM record with SoS fields
        
    Returns:
        List of formatted lines
    """
    lines = []
    
    # Check if SoS data is available
    if metrics.sos_net_season is None and metrics.sos_net_last10 is None:
        lines.append("  Strength of Schedule: N/A")
        return lines
    
    lines.append(f"  Strength of Schedule (Avg Opp NetRtg):")
    lines.append(f"    Net: {format_sos_metric(metrics.sos_net_season, metrics.sos_net_last10, metrics.sos_net_delta)}")
    
    # Show Off/Def SoS if available
    if metrics.sos_off_season is not None or metrics.sos_off_last10 is not None:
        off_season_str = f"{metrics.sos_off_season:+.1f}" if metrics.sos_off_season is not None else "N/A"
        off_l10_str = f"{metrics.sos_off_last10:+.1f}" if metrics.sos_off_last10 is not None else "N/A"
        lines.append(f"    Off: Season {off_season_str} | L10 {off_l10_str}")
    if metrics.sos_def_season is not None or metrics.sos_def_last10 is not None:
        def_season_str = f"{metrics.sos_def_season:+.1f}" if metrics.sos_def_season is not None else "N/A"
        def_l10_str = f"{metrics.sos_def_last10:+.1f}" if metrics.sos_def_last10 is not None else "N/A"
        lines.append(f"    Def: Season {def_season_str} | L10 {def_l10_str}")
    
    return lines


def get_sos_context_note(metrics: TeamDailyMetricsORM) -> Optional[str]:
    """Get a contextual note about SoS and performance.
    
    This helps interpret performance changes in light of schedule difficulty.
    
    Args:
        metrics: TeamDailyMetricsORM record
        
    Returns:
        Context note or None if not applicable
    """
    if metrics.sos_net_delta is None or metrics.net_rtg_delta is None:
        return None
    
    sos_delta = metrics.sos_net_delta
    perf_delta = metrics.net_rtg_delta
    
    # Performance up + Schedule easier = suspect improvement
    if perf_delta > 3 and sos_delta < -2:
        return "⚠️ Improved vs easier schedule - may regress"
    
    # Performance up + Schedule harder = legitimate improvement
    if perf_delta > 3 and sos_delta > 2:
        return "✅ Improved vs harder schedule - legitimate surge"
    
    # Performance down + Schedule harder = schedule-related decline
    if perf_delta < -3 and sos_delta > 2:
        return "📊 Decline vs harder schedule - may not be as bad"
    
    # Performance down + Schedule easier = concerning decline
    if perf_delta < -3 and sos_delta < -2:
        return "🚨 Decline vs easier schedule - concerning"
    
    return None


def format_odds_american(decimal_odds: float) -> str:
    """Convert decimal odds to American format string.
    
    Args:
        decimal_odds: Decimal odds (e.g., 1.370)
        
    Returns:
        American odds string (e.g., "-270" or "+370")
    """
    if decimal_odds is None:
        return "N/A"
    
    if decimal_odds >= 2.0:
        american = int((decimal_odds - 1) * 100)
        return f"+{american}"
    else:
        american = int(-100 / (decimal_odds - 1))
        return str(american)


def format_game_odds(odds_list: List[GameOddsORM], home_team: TeamORM, away_team: TeamORM) -> List[str]:
    """Format odds for a game.
    
    Args:
        odds_list: List of GameOddsORM records for this game
        home_team: Home team ORM
        away_team: Away team ORM
        
    Returns:
        List of formatted lines
    """
    lines = []
    
    if not odds_list:
        lines.append("  📊 Betting Lines: Not available")
        return lines
    
    lines.append("  📊 Betting Lines:")
    
    # Get consensus (average across US books)
    us_odds = [o for o in odds_list if o.country_code == 'US']
    
    if us_odds:
        # Calculate averages
        home_mls = [o.home_ml_odds for o in us_odds if o.home_ml_odds]
        away_mls = [o.away_ml_odds for o in us_odds if o.away_ml_odds]
        spreads = [o.home_spread for o in us_odds if o.home_spread is not None]
        
        if home_mls and away_mls:
            avg_home_ml = sum(home_mls) / len(home_mls)
            avg_away_ml = sum(away_mls) / len(away_mls)
            
            home_ml_str = format_odds_american(avg_home_ml)
            away_ml_str = format_odds_american(avg_away_ml)
            
            # Determine favorite
            if avg_home_ml < avg_away_ml:
                favorite = f"🏠 {home_team.abbreviation}"
            else:
                favorite = f"🛫 {away_team.abbreviation}"
            
            lines.append(f"    Moneyline: {home_team.abbreviation} {home_ml_str} | {away_team.abbreviation} {away_ml_str} (Fav: {favorite})")
        
        if spreads:
            avg_spread = sum(spreads) / len(spreads)
            spread_str = f"{avg_spread:+.1f}" if avg_spread != 0 else "PK"
            lines.append(f"    Spread: {home_team.abbreviation} {spread_str} ({len(spreads)} books)")
        
        # Show movement if available
        for odds in us_odds[:1]:  # Just show one book's movement
            if odds.home_ml_trend:
                trend_emoji = "📈" if odds.home_ml_trend == "up" else "📉" if odds.home_ml_trend == "down" else ""
                if trend_emoji:
                    lines.append(f"    Line Movement: {home_team.abbreviation} ML trending {odds.home_ml_trend} {trend_emoji}")
                break
    else:
        lines.append("    No US sportsbook data available")
    
    return lines


def format_metric_with_delta(season_val, lastn_val, delta_val, is_defense=False, is_percentage=False, percentage_threshold=0.02):
    """Format a metric showing season, lastN, and delta.
    
    Args:
        season_val: Season value
        lastn_val: Last N value
        delta_val: Delta value
        is_defense: If True, positive delta is bad (invert coloring)
        is_percentage: If True, multiply by 100 and show as percentage
        percentage_threshold: Threshold for percentage deltas (default 0.02 = 2 percentage points)
    
    Returns:
        Formatted string with emoji indicators
    """
    if season_val is None or lastn_val is None or delta_val is None:
        return "N/A"
    
    # Convert to percentages if needed
    if is_percentage:
        season_val = season_val * 100
        lastn_val = lastn_val * 100
        delta_val = delta_val * 100
        threshold = percentage_threshold * 100  # Convert to percentage points
    else:
        threshold = 2
    
    # Determine if delta is good or bad
    if is_defense:
        # For defense, negative delta is good (lower rating = better)
        is_improving = delta_val < -threshold
        is_declining = delta_val > threshold
    else:
        # For offense/pace, positive delta is good
        is_improving = delta_val > threshold
        is_declining = delta_val < -threshold
    
    # Add emoji
    if is_improving:
        emoji = "📈"
    elif is_declining:
        emoji = "📉"
    else:
        emoji = "➖"
    
    if is_percentage:
        return f"{season_val:>6.1f}% → {lastn_val:>6.1f}% ({delta_val:>+6.1f}pp) {emoji}"
    else:
        return f"{season_val:>6.1f} → {lastn_val:>6.1f} ({delta_val:>+6.1f}) {emoji}"


def format_team_metrics(metrics: TeamDailyMetricsORM, include_sos: bool = True) -> List[str]:
    """Format team metrics for display.
    
    Args:
        metrics: TeamDailyMetricsORM record
        include_sos: Whether to include Strength of Schedule section
    
    Returns:
        List of formatted lines
    """
    lines = []
    
    lines.append(f"  Core Metrics (Season → Last {metrics.window_size} → Delta):")
    lines.append(f"    OffRtg:  {format_metric_with_delta(metrics.off_rtg_season, metrics.off_rtg_lastn, metrics.off_rtg_delta)}")
    lines.append(f"    DefRtg:  {format_metric_with_delta(metrics.def_rtg_season, metrics.def_rtg_lastn, metrics.def_rtg_delta, is_defense=True)}")
    lines.append(f"    NetRtg:  {format_metric_with_delta(metrics.net_rtg_season, metrics.net_rtg_lastn, metrics.net_rtg_delta)}")
    lines.append(f"    Pace:    {format_metric_with_delta(metrics.pace_season, metrics.pace_lastn, metrics.pace_delta)}")
    
    lines.append(f"  Four Factors:")
    lines.append(f"    eFG%:    {format_metric_with_delta(metrics.efg_season, metrics.efg_lastn, metrics.efg_delta, is_percentage=True)}")
    lines.append(f"    TOV%:    {format_metric_with_delta(metrics.tov_pct_season, metrics.tov_pct_lastn, metrics.tov_pct_delta, is_defense=True, is_percentage=True)}")
    lines.append(f"    FTR:     {format_metric_with_delta(metrics.ftr_season, metrics.ftr_lastn, metrics.ftr_delta, is_percentage=True)}")
    
    # Only show scoring if available
    if metrics.pct_pts_3pt_season is not None:
        lines.append(f"  Scoring Profile (% of Total Points):")
        lines.append(f"    3PT:     {format_metric_with_delta(metrics.pct_pts_3pt_season, metrics.pct_pts_3pt_lastn, metrics.pct_pts_3pt_delta, is_percentage=True)}")
        if metrics.pct_pts_ft_season is not None:
            lines.append(f"    FT:      {format_metric_with_delta(metrics.pct_pts_ft_season, metrics.pct_pts_ft_lastn, metrics.pct_pts_ft_delta, is_percentage=True)}")
    
    # Add Strength of Schedule section
    if include_sos:
        sos_lines = format_sos_summary(metrics)
        lines.extend(sos_lines)
        
        # Add context note if applicable
        context_note = get_sos_context_note(metrics)
        if context_note:
            lines.append(f"    💡 {context_note}")
    
    return lines


def format_flags(flags: List[TeamDailyFlagsORM]) -> str:
    """Format team flags for display.
    
    Args:
        flags: List of flag records
    
    Returns:
        Formatted string
    """
    if not flags:
        return "None"
    
    # Group by flag type
    flag_strs = []
    for flag in sorted(flags, key=lambda f: f.severity or 0, reverse=True):
        severity_str = f" ({flag.severity:.1f})" if flag.severity else ""
        flag_strs.append(f"🏷️  {flag.flag_type}{severity_str}")
    
    return ", ".join(flag_strs)


def format_game_environment(env: GameEnvironmentDailyORM, home_team: TeamORM, away_team: TeamORM,
                           home_schedule: Optional[TeamScheduleFactorsORM] = None,
                           away_schedule: Optional[TeamScheduleFactorsORM] = None,
                           odds_list: Optional[List[GameOddsORM]] = None) -> List[str]:
    """Format game environment for display.
    
    Args:
        env: GameEnvironmentDailyORM record
        home_team: Home team ORM
        away_team: Away team ORM
        home_schedule: Optional schedule factors for home team
        away_schedule: Optional schedule factors for away team
        odds_list: Optional list of odds for this game
    
    Returns:
        List of formatted lines
    """
    lines = []
    
    lines.append(f"  🏠 {home_team.name} vs 🛫 {away_team.name}")
    
    # Add betting odds first (most actionable info)
    if odds_list:
        odds_lines = format_game_odds(odds_list, home_team, away_team)
        lines.extend(odds_lines)
    
    # Schedule Factors Section
    if home_schedule or away_schedule:
        lines.append(f"  Schedule Factors:")
        if home_schedule:
            home_sched_str = format_schedule_factors_short(home_schedule)
            lines.append(f"    🏠 {home_team.abbreviation}: {home_sched_str}")
        if away_schedule:
            away_sched_str = format_schedule_factors_short(away_schedule)
            lines.append(f"    🛫 {away_team.abbreviation}: {away_sched_str}")
        
        # Highlight significant rest edges
        if home_schedule and home_schedule.rest_edge == 'advantage':
            lines.append(f"    📊 {home_team.abbreviation} has {home_schedule.rest_diff}+ day REST ADVANTAGE")
        elif away_schedule and away_schedule.rest_edge == 'advantage':
            lines.append(f"    📊 {away_team.abbreviation} has {away_schedule.rest_diff}+ day REST ADVANTAGE")
        
        # Highlight B2B situations
        if home_schedule and home_schedule.is_b2b:
            lines.append(f"    ⚠️ {home_team.abbreviation} on BACK-TO-BACK")
        if away_schedule and away_schedule.is_b2b:
            lines.append(f"    ⚠️ {away_team.abbreviation} on BACK-TO-BACK")
    
    lines.append(f"  Matchup:")
    lines.append(f"    Home OffRtg: {env.home_off_rtg_lastn:.1f} | Away DefRtg: {env.away_def_rtg_lastn:.1f}")
    lines.append(f"    Away OffRtg: {env.away_off_rtg_lastn:.1f} | Home DefRtg: {env.home_def_rtg_lastn:.1f}")
    lines.append(f"  Environment:")
    lines.append(f"    Pace Projection: {env.pace_projection:.1f} {'(Fast! 🏃)' if env.pace_projection > 102 else '(Slow 🐌)' if env.pace_projection < 96 else ''}")
    lines.append(f"    Scoring Index:   {env.scoring_env_index:.1f} {'(High Scoring! 🎯)' if env.scoring_env_index > 105 else '(Low Scoring 🛡️)' if env.scoring_env_index < 95 else ''}")
    if env.three_env_index:
        lines.append(f"    3PT Index:       {env.three_env_index:.1f} {'(3PT Fest! 🎯)' if env.three_point_fest else ''}")
    lines.append(f"    Chaos Index:     {env.chaos_index:.1f} {'(Chaotic! 🌪️)' if env.chaos_index > 110 else ''}")
    
    # Tags
    if env.tags:
        lines.append(f"  Tags: {', '.join(env.tags)}")
    
    # Flags
    flag_emojis = []
    if env.three_point_fest:
        flag_emojis.append("3️⃣ Three-Point Fest")
    if env.paint_battle:
        flag_emojis.append("🏀 Paint Battle")
    if env.glass_war:
        flag_emojis.append("🥊 Glass War")
    if env.whistle_heavy:
        flag_emojis.append("🚨 Whistle Heavy")
    
    if flag_emojis:
        lines.append(f"  Special Flags: {', '.join(flag_emojis)}")
    
    return lines


def generate_report(target_date: date, season: str, output_file: str):
    """Generate comprehensive team analytics report."""
    lines = []
    # Track counts for final output
    games_count = 0
    team_metrics_count = 0
    game_environments_count = 0
    schedule_factors_count = 0
    odds_count = 0
    
    with get_db_context() as db:
        # Get today's games
        games = GameScheduleORM.get_by_date(target_date, db=db)
        games_count = len(games)
        
        # Get team metrics (most recent for each team)
        team_metrics = db.query(TeamDailyMetricsORM).filter(
            TeamDailyMetricsORM.season == season,
            TeamDailyMetricsORM.window_size == 10
        ).order_by(
            TeamDailyMetricsORM.team_id,
            TeamDailyMetricsORM.stat_date.desc()
        ).distinct(TeamDailyMetricsORM.team_id).all()
        team_metrics_count = len(team_metrics)
        
        # Get team flags
        team_flags_all = db.query(TeamDailyFlagsORM).filter(
            TeamDailyFlagsORM.season == season
        ).order_by(TeamDailyFlagsORM.stat_date.desc()).all()
        
        # Group flags by team
        flags_by_team = defaultdict(list)
        for flag in team_flags_all:
            flags_by_team[flag.team_id].append(flag)
        
        # Get game environments for today
        game_environments = db.query(GameEnvironmentDailyORM).filter(
            GameEnvironmentDailyORM.game_date == target_date,
            GameEnvironmentDailyORM.season == season
        ).all()
        game_environments_count = len(game_environments)
        
        # Get schedule factors for today
        schedule_factors = TeamScheduleFactorsORM.get_by_date(target_date, db=db)
        schedule_factors_count = len(schedule_factors)
        
        # Group schedule factors by team_id and game_id
        schedule_by_team = {}
        schedule_by_game = defaultdict(dict)
        for sf in schedule_factors:
            schedule_by_team[sf.team_id] = sf
            schedule_by_game[sf.game_id][sf.team_id] = sf
        
        # Get odds for today's games
        game_odds = GameOddsORM.get_by_date(target_date, country_code='US', db=db)
        odds_count = len(game_odds)
        
        # Group odds by game_id
        odds_by_game = defaultdict(list)
        for odds in game_odds:
            odds_by_game[odds.game_id].append(odds)
        
        # Header
        lines.append("=" * 120)
        lines.append(f"TEAM ANALYTICS REPORT - {target_date.strftime('%A, %B %d, %Y')}")
        lines.append(f"Season: {season} | {len(games)} Game(s) | {len(team_metrics)} Teams | {len(odds_by_game)} Games with Odds")
        lines.append("=" * 120)
        lines.append("")
        
        # Headlines Section - Quick summary of key storylines
        lines.append("🔥 TODAY'S HEADLINES")
        lines.append("-" * 120)
        
        # Top improvers by Net Rating
        teams_with_delta = [m for m in team_metrics if m.net_rtg_delta is not None]
        if teams_with_delta:
            top_improvers = sorted(teams_with_delta, key=lambda m: m.net_rtg_delta, reverse=True)[:3]
            improver_names = [f"{m.team_name} (+{m.net_rtg_delta:.1f})" for m in top_improvers]
            lines.append(f"  📈 Biggest Improvers: {', '.join(improver_names)}")
            
            top_decliners = sorted(teams_with_delta, key=lambda m: m.net_rtg_delta)[:3]
            decliner_names = [f"{m.team_name} ({m.net_rtg_delta:.1f})" for m in top_decliners]
            lines.append(f"  📉 Biggest Decliners: {', '.join(decliner_names)}")
        
        # Schedule edges - teams with rest advantages today
        if schedule_factors:
            b2b_teams = [sf for sf in schedule_factors if sf.is_b2b]
            if b2b_teams:
                b2b_names = []
                for sf in b2b_teams[:5]:
                    team = TeamORM.get_by_id(sf.team_id, db=db)
                    if team:
                        b2b_names.append(team.abbreviation)
                lines.append(f"  🔴 Teams on B2B: {', '.join(b2b_names)}")
            
            rest_advantages = [sf for sf in schedule_factors if sf.rest_edge == 'advantage']
            if rest_advantages:
                rest_edges = []
                for sf in sorted(rest_advantages, key=lambda x: x.rest_diff or 0, reverse=True)[:3]:
                    team = TeamORM.get_by_id(sf.team_id, db=db)
                    if team:
                        rest_edges.append(f"{team.abbreviation} (+{sf.rest_diff}d)")
                if rest_edges:
                    lines.append(f"  ✅ Biggest Rest Advantages: {', '.join(rest_edges)}")
        
        # SoS insights - teams with context
        teams_with_sos = [m for m in team_metrics if m.sos_net_delta is not None and m.net_rtg_delta is not None]
        if teams_with_sos:
            # Teams improving vs harder schedule (legit)
            legit_improvers = [m for m in teams_with_sos 
                             if m.net_rtg_delta > 3 and m.sos_net_delta > 2]
            if legit_improvers:
                legit_names = [m.team_name for m in legit_improvers[:2]]
                lines.append(f"  ✅ Improving vs Harder Schedule: {', '.join(legit_names)}")
            
            # Teams declining vs easier schedule (concerning)
            concerning = [m for m in teams_with_sos 
                         if m.net_rtg_delta < -3 and m.sos_net_delta < -2]
            if concerning:
                concerning_names = [m.team_name for m in concerning[:2]]
                lines.append(f"  🚨 Declining vs Easier Schedule: {', '.join(concerning_names)}")
        
        # Game environments - highest scoring
        if game_environments:
            high_scoring_games = sorted(game_environments, key=lambda e: e.scoring_env_index, reverse=True)[:3]
            scoring_matchups = []
            for env in high_scoring_games:
                home_team = TeamORM.get_by_id(env.home_team_id, db=db)
                away_team = TeamORM.get_by_id(env.away_team_id, db=db)
                if home_team and away_team:
                    scoring_matchups.append(f"{home_team.abbreviation}-{away_team.abbreviation} ({env.scoring_env_index:.1f})")
            if scoring_matchups:
                lines.append(f"  🎯 Highest Scoring Environments: {', '.join(scoring_matchups)}")
            
            # Fastest pace games
            fast_pace_games = sorted(game_environments, key=lambda e: e.pace_projection, reverse=True)[:3]
            pace_matchups = []
            for env in fast_pace_games:
                home_team = TeamORM.get_by_id(env.home_team_id, db=db)
                away_team = TeamORM.get_by_id(env.away_team_id, db=db)
                if home_team and away_team:
                    pace_matchups.append(f"{home_team.abbreviation}-{away_team.abbreviation} ({env.pace_projection:.1f})")
            if pace_matchups:
                lines.append(f"  🏃 Fastest Pace Games: {', '.join(pace_matchups)}")
        
        lines.append("")
        
        # Odds Summary Section (before game environments)
        if odds_by_game:
            lines.append("=" * 120)
            lines.append(f"💰 BETTING LINES OVERVIEW ({len(odds_by_game)} Games)")
            lines.append("=" * 120)
            lines.append("")
            lines.append(f"{'Matchup':<40} | {'Home ML':>10} | {'Away ML':>10} | {'Spread':>10} | {'Favorite'}")
            lines.append("-" * 120)
            
            for game_id, odds_list in odds_by_game.items():
                if not odds_list:
                    continue
                    
                # Get team info
                first_odds = odds_list[0]
                home_team = TeamORM.get_by_id(first_odds.home_team_id, db=db)
                away_team = TeamORM.get_by_id(first_odds.away_team_id, db=db)
                
                if not home_team or not away_team:
                    continue
                
                matchup = f"{home_team.abbreviation} vs {away_team.abbreviation}"
                
                # Calculate averages
                home_mls = [o.home_ml_odds for o in odds_list if o.home_ml_odds]
                away_mls = [o.away_ml_odds for o in odds_list if o.away_ml_odds]
                spreads = [o.home_spread for o in odds_list if o.home_spread is not None]
                
                home_ml_str = "N/A"
                away_ml_str = "N/A"
                spread_str = "N/A"
                favorite = "N/A"
                
                if home_mls and away_mls:
                    avg_home_ml = sum(home_mls) / len(home_mls)
                    avg_away_ml = sum(away_mls) / len(away_mls)
                    home_ml_str = format_odds_american(avg_home_ml)
                    away_ml_str = format_odds_american(avg_away_ml)
                    
                    if avg_home_ml < avg_away_ml:
                        favorite = f"🏠 {home_team.abbreviation}"
                    else:
                        favorite = f"🛫 {away_team.abbreviation}"
                
                if spreads:
                    avg_spread = sum(spreads) / len(spreads)
                    spread_str = f"{home_team.abbreviation} {avg_spread:+.1f}"
                
                lines.append(f"{matchup:<40} | {home_ml_str:>10} | {away_ml_str:>10} | {spread_str:>10} | {favorite}")
            
            lines.append("")
        
        lines.append("")
        
        # Section 1: Today's Game Environments
        if game_environments:
            lines.append("=" * 120)
            lines.append(f"📅 TODAY'S GAME ENVIRONMENTS ({len(game_environments)} Games)")
            lines.append("=" * 120)
            lines.append("")
            
            for env in game_environments:
                home_team = TeamORM.get_by_id(env.home_team_id, db=db)
                away_team = TeamORM.get_by_id(env.away_team_id, db=db)
                
                if home_team and away_team:
                    # Get schedule factors for both teams in this game
                    game_schedules = schedule_by_game.get(env.game_id, {})
                    home_schedule = game_schedules.get(env.home_team_id)
                    away_schedule = game_schedules.get(env.away_team_id)
                    
                    # Get odds for this game (convert game_id to string format with leading zeros)
                    game_id_str = f"{env.game_id:010d}" if isinstance(env.game_id, int) else str(env.game_id)
                    game_odds_list = odds_by_game.get(game_id_str, [])
                    
                    lines.append("-" * 120)
                    env_lines = format_game_environment(
                        env, home_team, away_team,
                        home_schedule=home_schedule,
                        away_schedule=away_schedule,
                        odds_list=game_odds_list
                    )
                    lines.extend(env_lines)
                    lines.append("")
        else:
            lines.append("=" * 120)
            lines.append(f"📅 NO GAME ENVIRONMENTS CALCULATED FOR {target_date.strftime('%Y-%m-%d')}")
            lines.append("=" * 120)
            lines.append("")
        
        lines.append("")
        
        # Section 2: Teams Playing Today (Detailed Metrics + Flags)
        if games:
            # Get unique team IDs from today's games
            todays_team_ids = set()
            for game in games:
                todays_team_ids.add(game['team_id'])
                todays_team_ids.add(game['opponent_team_id'])
            
            todays_metrics = [m for m in team_metrics if m.team_id in todays_team_ids]
            
            if todays_metrics:
                lines.append("=" * 120)
                lines.append(f"🏀 TEAMS PLAYING TODAY ({len(todays_metrics)} Teams)")
                lines.append("=" * 120)
                lines.append("")
                
                # Sort by team name
                todays_metrics_sorted = sorted(todays_metrics, key=lambda m: m.team_name)
                
                for metrics in todays_metrics_sorted:
                    lines.append("-" * 120)
                    lines.append(f"🏀 {metrics.team_name} (Last Updated: {metrics.stat_date.strftime('%Y-%m-%d')})")
                    lines.append("-" * 120)
                    
                    # Schedule Factors (if available for today)
                    team_schedule = schedule_by_team.get(metrics.team_id)
                    if team_schedule:
                        sched_lines = format_schedule_factors_detail(team_schedule, metrics.team_name)
                        lines.extend(sched_lines)
                    
                    # Metrics (now includes SoS)
                    metric_lines = format_team_metrics(metrics, include_sos=True)
                    lines.extend(metric_lines)
                    
                    # Flags
                    team_flags = flags_by_team.get(metrics.team_id, [])
                    recent_flags = [f for f in team_flags if f.stat_date == metrics.stat_date]
                    lines.append(f"  Active Flags: {format_flags(recent_flags)}")
                    
                    lines.append("")
        
        lines.append("")
        
        # Section 3: All Teams Summary (Sorted by Key Metrics)
        lines.append("=" * 120)
        lines.append("📊 ALL TEAMS SUMMARY")
        lines.append("=" * 120)
        lines.append("")
        
        # Top teams by Net Rating (last N)
        teams_with_netrtg = [m for m in team_metrics if m.net_rtg_lastn is not None]
        if teams_with_netrtg:
            lines.append("🔥 TOP 10 TEAMS BY NET RATING (Last 10 Games)")
            lines.append("-" * 120)
            lines.append(f"{'Rank':<5} | {'Team':<30} | {'NetRtg':>8} | {'OffRtg':>8} | {'DefRtg':>8} | {'Pace':>7} | {'Flags'}")
            lines.append("-" * 120)
            
            top_netrtg = sorted(teams_with_netrtg, key=lambda m: m.net_rtg_lastn, reverse=True)[:10]
            for idx, metrics in enumerate(top_netrtg, 1):
                team_flags = flags_by_team.get(metrics.team_id, [])
                recent_flags = [f for f in team_flags if f.stat_date == metrics.stat_date]
                flag_types = [f.flag_type for f in recent_flags[:3]]  # Top 3 flags
                
                lines.append(
                    f"{idx:<5} | {metrics.team_name:<30} | "
                    f"{metrics.net_rtg_lastn:>8.1f} | "
                    f"{metrics.off_rtg_lastn:>8.1f} | "
                    f"{metrics.def_rtg_lastn:>8.1f} | "
                    f"{metrics.pace_lastn:>7.1f} | "
                    f"{', '.join(flag_types) if flag_types else 'None'}"
                )
            
            lines.append("")
        
        # Biggest movers (Net Rating Delta)
        teams_with_delta = [m for m in team_metrics if m.net_rtg_delta is not None]
        if teams_with_delta:
            lines.append("📈 BIGGEST POSITIVE MOVERS (Net Rating Delta)")
            lines.append("-" * 120)
            lines.append(f"{'Rank':<5} | {'Team':<30} | {'Delta':>8} | {'Season':>8} | {'Last 10':>8} | {'Flags'}")
            lines.append("-" * 120)
            
            biggest_improvers = sorted(teams_with_delta, key=lambda m: m.net_rtg_delta, reverse=True)[:10]
            for idx, metrics in enumerate(biggest_improvers, 1):
                team_flags = flags_by_team.get(metrics.team_id, [])
                recent_flags = [f for f in team_flags if f.stat_date == metrics.stat_date]
                flag_types = [f.flag_type for f in recent_flags[:3]]
                
                lines.append(
                    f"{idx:<5} | {metrics.team_name:<30} | "
                    f"{metrics.net_rtg_delta:>+8.1f} | "
                    f"{metrics.net_rtg_season:>8.1f} | "
                    f"{metrics.net_rtg_lastn:>8.1f} | "
                    f"{', '.join(flag_types) if flag_types else 'None'}"
                )
            
            lines.append("")
            
            lines.append("📉 BIGGEST DECLINERS (Net Rating Delta)")
            lines.append("-" * 120)
            lines.append(f"{'Rank':<5} | {'Team':<30} | {'Delta':>8} | {'Season':>8} | {'Last 10':>8} | {'Flags'}")
            lines.append("-" * 120)
            
            biggest_decliners = sorted(teams_with_delta, key=lambda m: m.net_rtg_delta)[:10]
            for idx, metrics in enumerate(biggest_decliners, 1):
                team_flags = flags_by_team.get(metrics.team_id, [])
                recent_flags = [f for f in team_flags if f.stat_date == metrics.stat_date]
                flag_types = [f.flag_type for f in recent_flags[:3]]
                
                lines.append(
                    f"{idx:<5} | {metrics.team_name:<30} | "
                    f"{metrics.net_rtg_delta:>+8.1f} | "
                    f"{metrics.net_rtg_season:>8.1f} | "
                    f"{metrics.net_rtg_lastn:>8.1f} | "
                    f"{', '.join(flag_types) if flag_types else 'None'}"
                )
            
            lines.append("")
        
        # Section 4: Schedule Edges Summary (for today's games)
        if schedule_factors:
            lines.append("=" * 120)
            lines.append("📆 SCHEDULE EDGES SUMMARY")
            lines.append("=" * 120)
            lines.append("")
            
            # B2B teams
            b2b_teams = [sf for sf in schedule_factors if sf.is_b2b]
            lines.append(f"Back-to-Back Games: {len(b2b_teams)} team(s)")
            lines.append("-" * 120)
            if b2b_teams:
                for sf in b2b_teams:
                    team = TeamORM.get_by_id(sf.team_id, db=db)
                    opp = TeamORM.get_by_id(sf.opponent_id, db=db)
                    if team and opp:
                        rest_edge_str = f"vs {opp.abbreviation} ({sf.opponent_days_rest}d rest)" if sf.opponent_days_rest else f"vs {opp.abbreviation}"
                        lines.append(f"  🔴 {team.name:<30} {rest_edge_str}")
            else:
                lines.append("  No teams on B2B today")
            lines.append("")
            
            # 3-in-4 situations
            three_in_four = [sf for sf in schedule_factors if sf.is_3_in_4 and not sf.is_b2b]
            if three_in_four:
                lines.append(f"3-in-4 Nights (not B2B): {len(three_in_four)} team(s)")
                lines.append("-" * 120)
                for sf in three_in_four:
                    team = TeamORM.get_by_id(sf.team_id, db=db)
                    if team:
                        lines.append(f"  🟠 {team.name:<30} ({sf.days_rest}d rest, {sf.games_last_4} games in last 4 days)")
                lines.append("")
            
            # Rest advantages
            rest_advantages = [sf for sf in schedule_factors if sf.rest_edge == 'advantage']
            lines.append(f"Rest Advantages (2+ day edge): {len(rest_advantages)} team(s)")
            lines.append("-" * 120)
            if rest_advantages:
                lines.append(f"{'Team':<30} | {'Rest':>6} | {'Opp Rest':>8} | {'Edge':>6} | {'Opponent'}")
                lines.append("-" * 120)
                for sf in sorted(rest_advantages, key=lambda x: x.rest_diff or 0, reverse=True):
                    team = TeamORM.get_by_id(sf.team_id, db=db)
                    opp = TeamORM.get_by_id(sf.opponent_id, db=db)
                    if team and opp:
                        lines.append(
                            f"  {team.name:<28} | {sf.days_rest:>4}d  | {sf.opponent_days_rest:>6}d  | +{sf.rest_diff:>4}d | vs {opp.abbreviation}"
                        )
            else:
                lines.append("  No significant rest advantages today")
            lines.append("")
        
        # Section 5: Strength of Schedule Summary
        teams_with_sos = [m for m in team_metrics if m.sos_net_season is not None]
        if teams_with_sos:
            lines.append("=" * 120)
            lines.append("💪 STRENGTH OF SCHEDULE SUMMARY")
            lines.append("=" * 120)
            lines.append("")
            
            # Toughest schedules (season)
            toughest_season = sorted(teams_with_sos, key=lambda m: m.sos_net_season or 0, reverse=True)[:5]
            lines.append("Toughest Season Schedules (Avg Opp NetRtg):")
            lines.append("-" * 120)
            for idx, m in enumerate(toughest_season, 1):
                lines.append(f"  {idx}. {m.team_name:<28} SoS: {m.sos_net_season:+.1f}")
            lines.append("")
            
            # Easiest schedules (season)
            easiest_season = sorted(teams_with_sos, key=lambda m: m.sos_net_season or 0)[:5]
            lines.append("Easiest Season Schedules:")
            lines.append("-" * 120)
            for idx, m in enumerate(easiest_season, 1):
                lines.append(f"  {idx}. {m.team_name:<28} SoS: {m.sos_net_season:+.1f}")
            lines.append("")
            
            # Schedule getting harder (positive delta)
            teams_with_sos_delta = [m for m in teams_with_sos if m.sos_net_delta is not None]
            if teams_with_sos_delta:
                harder_lately = sorted(teams_with_sos_delta, key=lambda m: m.sos_net_delta, reverse=True)[:5]
                lines.append("Schedule Getting Harder (SoS L10 vs Season):")
                lines.append("-" * 120)
                for idx, m in enumerate(harder_lately, 1):
                    lines.append(
                        f"  {idx}. {m.team_name:<28} Season: {m.sos_net_season:+.1f} → L10: {m.sos_net_last10:+.1f} ({m.sos_net_delta:+.1f})"
                    )
                lines.append("")
                
                easier_lately = sorted(teams_with_sos_delta, key=lambda m: m.sos_net_delta)[:5]
                lines.append("Schedule Getting Easier:")
                lines.append("-" * 120)
                for idx, m in enumerate(easier_lately, 1):
                    lines.append(
                        f"  {idx}. {m.team_name:<28} Season: {m.sos_net_season:+.1f} → L10: {m.sos_net_last10:+.1f} ({m.sos_net_delta:+.1f})"
                    )
                lines.append("")
        
        # Section 6: Flag Summary
        lines.append("=" * 120)
        lines.append("🏷️  TEAM FLAGS SUMMARY")
        lines.append("=" * 120)
        lines.append("")
        
        # Count flags by type
        flag_counts = defaultdict(int)
        for flag in team_flags_all:
            flag_counts[flag.flag_type] += 1
        
        if flag_counts:
            lines.append(f"Total Flags: {len(team_flags_all)} across {len(flags_by_team)} teams")
            lines.append("")
            lines.append("Flag Distribution:")
            lines.append("-" * 120)
            for flag_type, count in sorted(flag_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"  {flag_type:<30}: {count} teams")
        else:
            lines.append("No flags generated")
        
        lines.append("")
        
        # Show teams with most flags
        teams_by_flag_count = []
        for team_id, flags_list in flags_by_team.items():
            recent_flags = [f for f in flags_list if any(m.team_id == team_id and m.stat_date == f.stat_date for m in team_metrics)]
            if recent_flags:
                team = TeamORM.get_by_id(team_id, db=db)
                team_name = team.name if team else f"Team {team_id}"
                teams_by_flag_count.append((team_name, len(recent_flags), recent_flags))
        
        if teams_by_flag_count:
            teams_by_flag_count.sort(key=lambda x: x[1], reverse=True)
            
            lines.append("Teams with Most Flags:")
            lines.append("-" * 120)
            for team_name, flag_count, flags_list in teams_by_flag_count[:10]:
                flag_types = [f.flag_type for f in flags_list]
                lines.append(f"  {team_name:<30}: {flag_count} flags - {', '.join(flag_types)}")
        
        lines.append("")
        lines.append("=" * 120)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 120)
    
    # Output
    output = "\n".join(lines)
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Team report saved to {output_file}")
        print(f"   {games_count} game(s), {team_metrics_count} teams, {game_environments_count} environments, {odds_count} odds records")
    else:
        print(output)


def main():
    parser = argparse.ArgumentParser(description='Generate team analytics report')
    parser.add_argument('--date', type=str, help='Date (YYYY-MM-DD)', default=None)
    parser.add_argument('--output', type=str, help='Output file path', 
                       default=f"todays_teams_report_{datetime.now().strftime('%Y%m%d')}.txt")
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

