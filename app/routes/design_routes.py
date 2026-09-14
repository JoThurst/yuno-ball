"""Read-only product design labs backed by the canonical analytics payloads."""

from datetime import date, datetime
import logging

from flask import Blueprint, render_template, request

from app.middleware.security import secure_endpoint

logger = logging.getLogger(__name__)

design_bp = Blueprint("design", __name__, url_prefix="/design")


PROGRAM_STATUS = (
    {
        "key": "DAILY",
        "title": "Daily Intelligence V1",
        "state": "shipped",
        "state_label": "SHIPPED",
        "summary": "Public descriptive slate with historical date and matchup destinations.",
        "next": "Maintain the descriptive contract as live season evidence arrives",
        "steps": (("Package", "done"), ("Public route", "done"), ("History", "done"), ("Polish + QA", "done")),
    },
    {
        "key": "C7",
        "title": "Canonical player facts",
        "state": "shipped",
        "state_label": "FOUNDATION SHIPPED",
        "summary": "Traditional and Advanced V3 historical foundation for six Regular Seasons.",
        "next": "First 2026-27 completed-game smoke",
        "steps": (("Historical", "done"), ("Reconcile", "done"), ("Daily bridge", "done"), ("Smoke", "waiting")),
    },
    {
        "key": "G",
        "title": "Baseline game models",
        "state": "active",
        "state_label": "RESEARCH ACTIVE",
        "summary": "Frozen feature-family comparison is complete; calibration and publication remain gated.",
        "next": "Continue monitoring; prediction publication remains gated",
        "steps": (("Inputs", "done"), ("Baselines", "done"), ("Held-out", "done"), ("Production", "blocked")),
    },
    {
        "key": "H1",
        "title": "Role baseline",
        "state": "active",
        "state_label": "EVIDENCE ACTIVE",
        "summary": "Durable role history and strict-cutoff baseline projections are implemented.",
        "next": "Forward timing evidence and pre-registered calibration",
        "steps": (("Schema", "done"), ("Replay", "done"), ("Timing", "blocked"), ("Consumer", "blocked")),
    },
    {
        "key": "BRIDGE",
        "title": "2026–27 game bridge",
        "state": "waiting",
        "state_label": "WAITING ON SEASON",
        "summary": "Quiet-day behavior is safe; the completed-game path is wired.",
        "next": "Run Traditional → Advanced → C5 → replay on first completed game",
        "steps": (("Schedule", "done"), ("No-op", "done"), ("First game", "waiting"), ("Replay", "waiting")),
    },
    {
        "key": "I",
        "title": "Odds observation pilot",
        "state": "active",
        "state_label": "FORWARD PILOT READY",
        "summary": "One read-only SportsGameOdds probe and fixture pair review passed; source approval remains gated.",
        "next": "Canonical identity mapping, broader coverage, and licensing check",
        "steps": (("Contract", "done"), ("Adapter", "done"), ("Transport", "done"), ("Pair review", "done")),
    },
)

STATUS_GATES = (
    ("Historical Daily slice", "complete", "Public descriptive surface and permanent historical destinations"),
    ("G research gates", "complete", "Held-out, stability, subgroup, and calibration evidence recorded"),
    ("H1 apply/replay", "complete", "32,515 role-history rows, 216 baseline rows, zero natural-key duplicates"),
    ("Odds provider contract", "complete", "SportsGameOdds request guard and provider-shape normalizer are tested"),
    ("Forward source timing", "active", "Collection-time timestamps must precede future target tipoffs"),
    ("2026–27 smoke proof", "waiting", "Requires the first completed game in the season"),
    ("Odds source probe", "complete", "One request returned HTTP 200 with a normalized NBA event and provider timestamps; no writes"),
)

STATUS_SCORECARD = (
    {"label": "Gate completion", "value": "71%", "detail": "5 of 7 tracked gates have evidence", "tone": "good"},
    {"label": "Blocked or waiting", "value": "14%", "detail": "1 of 7 gates waits on season evidence", "tone": "wait"},
    {"label": "Active work", "value": "14%", "detail": "Forward timing can progress now", "tone": "active"},
)

STATUS_EVENTS = (
    ("09.13", "SportsGameOdds probe passed", "One read-only HTTP 200 response normalized one event, ten game markets, 48 bookmaker rows, and 48 provider timestamps; no writes."),
    ("09.13", "Odds transport rechecked", "Bounded no-write dry-run still fails closed on the NBA CDN 403."),
    ("09.13", "Readiness cleanup green", "436 tests passed, 2 skipped; compileall passed; Alembic reports no new upgrade operations."),
    ("09.13", "Odds fixture pair review", "Spread-side lines canonicalize correctly; complete/incomplete/duplicate groups are reported and provider identity stays unresolved."),
    ("09.13", "Frozen G comparison", "All four variants passed coverage across 1,075 games in each approved season; schedule-inclusive variants passed subgroup review."),
    ("09.13", "Daily accessibility QA", "Skip link, semantic main landmark, loader label/failsafe, menu state, historical tipoff fallback, and route smoke are covered."),
    ("09.13", "G monitoring rerun", "Both 1,075-game held-out directions completed with no writes."),
    ("09.13", "Timing baseline recorded", "Two historical seasons show backfill timing; 2026-27 has no completed facts yet."),
    ("09.13", "H1 bridge hardened", "Successful C5 batches now advance role history atomically."),
    ("09.13", "Calibration protocol locked", "Four candidate bands and chronological decision thresholds are registered."),
    ("09.13", "Daily launch contract tested", "Public, empty, partial, provenance, and invalid-date states are covered."),
    ("09.12", "G research gates complete", "Monitoring continues; no production prediction is published."),
)


def _parse_lab_request():
    mode = request.args.get("mode", "demo")
    if mode == "current":
        return date.today(), None, "current"

    raw_date = request.args.get("date", "2025-03-03")
    try:
        target_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("date must use YYYY-MM-DD")
    return target_date, request.args.get("season", "2024-25"), "demo" if raw_date == "2025-03-03" else "custom"


@design_bp.route("/daily-v1")
@secure_endpoint()
def daily_v1_lab():
    """Interactive visual prototype for Daily Intelligence V1."""
    from app.services.daily_intelligence_service import build_daily_intelligence_v1

    try:
        target_date, season, mode = _parse_lab_request()
        package = build_daily_intelligence_v1(target_date=target_date, season=season)
        return render_template(
            "design/daily_v1_lab.html",
            package=package.to_dict(),
            mode=mode,
            requested_date=target_date.isoformat(),
            requested_season=season,
        )
    except ValueError as exc:
        return render_template("error.html", error=str(exc)), 400
    except Exception as exc:
        logger.exception("Daily Intelligence design lab failed")
        return render_template("error.html", error=str(exc)), 500


@design_bp.route("/status")
@secure_endpoint()
def program_status_lab():
    """Visual program status and gate map; read-only and repository-backed."""
    return render_template(
        "design/program_status.html",
        programs=PROGRAM_STATUS,
        gates=STATUS_GATES,
        scorecard=STATUS_SCORECARD,
        events=STATUS_EVENTS,
        reviewed="2026-09-13",
    )
