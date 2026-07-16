"""Daily slate pages — Fan Daily and Betting Daily."""

import logging
from datetime import datetime

from flask import Blueprint, render_template, request

from app.middleware.security import secure_endpoint

logger = logging.getLogger(__name__)

daily_bp = Blueprint("daily", __name__, url_prefix="/daily")


def _parse_date_arg():
    raw = request.args.get("date")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


@daily_bp.route("/")
@secure_endpoint()
def fan_daily():
    """Fan Daily — curated slate insights without betting framing."""
    from app.services.slate_service import get_fan_daily_data

    target_date = _parse_date_arg()
    season = request.args.get("season")
    try:
        data = get_fan_daily_data(target_date=target_date, season=season)
        return render_template("daily/fan_daily.html", **data)
    except Exception as e:
        logger.exception("Fan daily failed")
        return render_template("error.html", error=str(e)), 500


@daily_bp.route("/betting")
@secure_endpoint()
def betting_daily():
    """Betting Daily — odds, edges, prop-oriented player context."""
    from app.services.slate_service import get_betting_daily_data

    target_date = _parse_date_arg()
    season = request.args.get("season")
    try:
        data = get_betting_daily_data(target_date=target_date, season=season)
        return render_template("daily/betting_daily.html", **data)
    except Exception as e:
        logger.exception("Betting daily failed")
        return render_template("error.html", error=str(e)), 500
