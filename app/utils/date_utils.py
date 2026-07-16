"""Date and timezone utility functions for NBA game dates.

This module provides utilities for converting UTC game dates to EST/EDT
for proper display and chronological ordering.
"""

from datetime import datetime
from typing import Optional
import pytz


def convert_utc_to_est_edt(utc_datetime: Optional[datetime]) -> Optional[datetime]:
    """Convert UTC datetime to EST/EDT timezone.
    
    Args:
        utc_datetime: UTC datetime object
        
    Returns:
        datetime in EST/EDT timezone, or None if input is None
    """
    if not utc_datetime:
        return None
    
    # Ensure input is timezone-aware (assume UTC if naive)
    if utc_datetime.tzinfo is None:
        utc_datetime = pytz.UTC.localize(utc_datetime)
    elif utc_datetime.tzinfo != pytz.UTC:
        # Convert to UTC first if it's in another timezone
        utc_datetime = utc_datetime.astimezone(pytz.UTC)
    
    # Convert to Eastern timezone (handles EST/EDT automatically)
    eastern = pytz.timezone('America/New_York')
    return utc_datetime.astimezone(eastern)


def format_game_date_for_display(utc_datetime: Optional[datetime], format_str: str = "%a %m/%d") -> str:
    """Format a UTC game datetime to EST/EDT for display.
    
    Args:
        utc_datetime: UTC datetime object or None
        format_str: strftime format string (default: "%a %m/%d")
        
    Returns:
        Formatted date string in EST/EDT, or empty string if None
    """
    if not utc_datetime:
        return ""
    
    est_datetime = convert_utc_to_est_edt(utc_datetime)
    if not est_datetime:
        return ""
    
    return est_datetime.strftime(format_str)


def get_game_date_est_edt(utc_datetime: Optional[datetime]) -> Optional[datetime]:
    """Get the date portion of a UTC datetime in EST/EDT.
    
    This is useful for grouping/filtering games by date in EST/EDT,
    which matches how the NBA schedules games.
    
    Args:
        utc_datetime: UTC datetime object
        
    Returns:
        datetime object with date in EST/EDT (time set to 00:00:00), or None
    """
    est_datetime = convert_utc_to_est_edt(utc_datetime)
    if not est_datetime:
        return None
    
    # Return just the date portion (midnight in EST/EDT)
    return est_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

