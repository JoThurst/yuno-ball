"""Read last ingest / validation success markers for UI freshness display."""

import json
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INGEST_MARKER = DATA_DIR / "last_ingest_success.json"
VALIDATION_MARKER = DATA_DIR / "last_validation.json"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _latest_validated_ingest() -> Dict[str, Any]:
    """Read the latest full validated daily run from durable PostgreSQL state."""
    try:
        from sqlalchemy import text

        from app.database import engine

        with engine.connect() as connection:
            candidates = connection.execute(
                text(
                    """SELECT run_id, season, target_date, finished_at, started_at, details
                       FROM ingestion_runs
                       WHERE run_type = 'daily_ingest'
                         AND status = 'success'
                         AND validation_status = 'passed'
                       ORDER BY finished_at DESC NULLS LAST
                       LIMIT 20"""
                )
            ).mappings().all()
        for run in candidates:
            details = run["details"] if isinstance(run["details"], dict) else {}
            if any(
                details.get(flag)
                for flag in ("validate_only", "fetch_only", "calc_only")
            ):
                continue
            timestamp = run["finished_at"] or run["started_at"]
            return {
                "timestamp": timestamp.isoformat() if timestamp else None,
                "run_id": run["run_id"],
                "season": run["season"],
                "target_date": (
                    run["target_date"].isoformat() if run["target_date"] else None
                ),
                "fetch_success": bool(details.get("fetch_success", True)),
                "calc_success": bool(details.get("calc_success", True)),
                "validation_success": True,
                "status": "success",
                "evidence_source": "ingestion_runs",
            }
    except Exception:
        # Freshness must degrade to an explicit unknown state instead of making
        # a PostgreSQL-backed product page unavailable.
        return {}
    return {}


def get_ingest_freshness() -> Dict[str, Any]:
    """Return freshness info for templates / APIs."""
    ingest = _read_json(INGEST_MARKER) or _latest_validated_ingest()
    validation = _read_json(VALIDATION_MARKER) or {}

    timestamp = ingest.get("timestamp")
    as_of = None
    if timestamp:
        try:
            as_of = datetime.fromisoformat(timestamp)
        except ValueError:
            as_of = None

    age_seconds = None
    if as_of:
        comparison_now = datetime.now(as_of.tzinfo) if as_of.tzinfo else datetime.now()
        age_seconds = max(0, int((comparison_now - as_of).total_seconds()))
    try:
        stale_after_hours = max(1, int(os.getenv("INGEST_STALE_AFTER_HOURS", "30")))
    except ValueError:
        stale_after_hours = 30
    is_stale = age_seconds is None or age_seconds > stale_after_hours * 3600
    marker_validation = ingest.get("validation_success")
    validation_ok = (
        marker_validation
        if marker_validation is not None
        else validation.get("ok")
    )
    is_complete = bool(
        ingest.get("status") == "success"
        and ingest.get("fetch_success")
        and ingest.get("calc_success")
        and validation_ok
    )

    return {
        "source": "daily_ingest",
        "evidence_source": ingest.get("evidence_source", "published_marker") if ingest else None,
        "run_id": ingest.get("run_id"),
        "timestamp": timestamp,
        "as_of": as_of,
        "as_of_display": as_of.strftime("%b %d, %Y %I:%M %p") if as_of else "Unknown",
        "target_date": ingest.get("target_date"),
        "season": ingest.get("season"),
        "status": ingest.get("status", "unknown"),
        "fetch_success": ingest.get("fetch_success"),
        "calc_success": ingest.get("calc_success"),
        "validation_ok": validation_ok,
        "validation_timestamp": validation.get("timestamp"),
        "is_complete": is_complete,
        "is_stale": is_stale,
        "age_seconds": age_seconds,
        "stale_after_hours": stale_after_hours,
        "has_marker": bool(ingest),
    }
