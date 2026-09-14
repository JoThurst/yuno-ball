"""Daily slate pages — Fan Daily and Betting Daily."""

import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request

from app.middleware.security import secure_endpoint

logger = logging.getLogger(__name__)

daily_bp = Blueprint("daily", __name__, url_prefix="/daily")
history_bp = Blueprint("history", __name__)


def _parse_date_arg():
    raw = request.args.get("date")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_date_arg_strict():
    raw = request.args.get("date")
    if not raw:
        return None, None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "date must use YYYY-MM-DD"


def _render_daily_page(target_date, season=None):
    from app.services.daily_intelligence_service import build_daily_intelligence_v1

    package = build_daily_intelligence_v1(target_date=target_date, season=season)
    return render_template(
        "daily/intelligence_v1.html",
        package=package.to_dict(),
        requested_date=target_date,
        requested_season=season,
        previous_date=target_date - timedelta(days=1),
        next_date=target_date + timedelta(days=1),
    )


@daily_bp.route("/")
@secure_endpoint()
def fan_daily():
    """Public Daily Intelligence V1 page."""
    target_date, error = _parse_date_arg_strict()
    target_date = target_date or datetime.now().date()
    season = request.args.get("season")
    if error:
        return render_template("error.html", error=error), 400
    try:
        return _render_daily_page(target_date, season=season)
    except Exception as e:
        logger.exception("Fan daily failed")
        return render_template("error.html", error=str(e)), 500


@daily_bp.route("/<date>")
@secure_endpoint()
def canonical_daily(date):
    """Permanent, indexable Daily Intelligence date page."""
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return render_template("error.html", error="date must use YYYY-MM-DD"), 404
    try:
        return _render_daily_page(target_date, season=request.args.get("season"))
    except Exception as exc:
        logger.exception("Canonical historical Daily page failed")
        return render_template("error.html", error=str(exc)), 500


@daily_bp.route("/archive")
@secure_endpoint()
def daily_archive():
    """Bounded historical date archive index."""
    from app.services.daily_archive_service import build_daily_archive_index

    season = request.args.get("season") or None
    try:
        page = build_daily_archive_index(
            season=season,
            limit=request.args.get("limit", 60),
            offset=request.args.get("offset", 0),
        )
        return render_template("daily/archive.html", **page)
    except (TypeError, ValueError):
        return render_template("error.html", error="limit and offset must be numeric"), 400
    except Exception as exc:
        logger.exception("Daily archive failed")
        return render_template("error.html", error=str(exc)), 500


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


@daily_bp.route("/api/v1")
@secure_endpoint()
def daily_intelligence_v1():
    """Read-only, versioned Daily Intelligence package for downstream consumers."""
    from app.services.daily_intelligence_service import build_daily_intelligence_v1

    target_date, error = _parse_date_arg_strict()
    if error:
        return jsonify({"error": "INVALID_DATE", "message": error}), 400
    season = request.args.get("season")
    try:
        package = build_daily_intelligence_v1(target_date=target_date, season=season)
        return jsonify(package.to_dict())
    except Exception as exc:
        logger.exception("Daily Intelligence V1 failed")
        return jsonify({"error": "DAILY_INTELLIGENCE_UNAVAILABLE", "message": str(exc)}), 500


@history_bp.route("/matchup/<date>/<matchup>")
@secure_endpoint()
def historical_matchup(date, matchup):
    """Permanent date-scoped matchup page using the Daily V1 contract."""
    from app.services.daily_archive_service import build_historical_matchup

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return render_template("error.html", error="date must use YYYY-MM-DD"), 404
    parts = matchup.upper().split("-")
    if len(parts) != 2 or not all(2 <= len(part) <= 5 and part.isalpha() for part in parts):
        return render_template("error.html", error="matchup must use AWAY-HOME abbreviations"), 404
    try:
        detail = build_historical_matchup(
            target_date,
            away_abbreviation=parts[0],
            home_abbreviation=parts[1],
            season=request.args.get("season"),
        )
        return render_template(
            "daily/matchup.html",
            **detail,
            requested_date=target_date,
        )
    except LookupError as exc:
        return render_template("error.html", error=str(exc)), 404
    except Exception as exc:
        logger.exception("Historical matchup failed")
        return render_template("error.html", error=str(exc)), 500
