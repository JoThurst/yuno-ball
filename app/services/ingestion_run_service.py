"""Durable ingestion run tracking with a PostgreSQL advisory job lock."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.database import engine, get_db_context
from app.models.ingestion_run_sqlalchemy import IngestionRunORM, IngestionTaskRunORM
from app.utils.season_utils import normalize_season, normalize_season_type


PIPELINE_LOCK_NAME = "yunoball:nba_daily_pipeline"
TERMINAL_RUN_STATUSES = {"success", "partial", "failed"}
TERMINAL_TASK_STATUSES = {"success", "skipped", "failed"}


class IngestionRunAlreadyActive(RuntimeError):
    """Raised when another process holds the daily pipeline lock."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _bounded(value: Optional[str], limit: int = 2000) -> Optional[str]:
    if value is None:
        return None
    return str(value)[:limit]


def _detect_code_version() -> str:
    configured = (
        os.getenv("YUNOBALL_CODE_VERSION")
        or os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
    )
    if configured:
        return configured[:128]
    try:
        repository_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()[:128] or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def infer_row_count(result: Any) -> Optional[int]:
    """Best-effort row count extraction without treating booleans as counts."""
    if result is None or isinstance(result, bool):
        return None
    if isinstance(result, int):
        return result
    if isinstance(result, (list, tuple, set, dict)):
        return len(result)
    return None


def start_task(
    run_id: str,
    task_name: str,
    *,
    source: Optional[str] = None,
    provider: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a running task record and return its immutable identifier."""
    task_run_id = str(uuid.uuid4())
    with get_db_context() as db:
        run_exists = db.get(IngestionRunORM, run_id)
        if run_exists is None:
            raise ValueError(f"Unknown ingestion run: {run_id}")
        db.add(
            IngestionTaskRunORM(
                task_run_id=task_run_id,
                run_id=run_id,
                task_name=task_name,
                source=source,
                provider=provider,
                status="running",
                details=details,
            )
        )
    return task_run_id


def finish_task(
    task_run_id: str,
    status: str,
    *,
    result: Any = None,
    rows_read: Optional[int] = None,
    rows_written: Optional[int] = None,
    error: Optional[BaseException] = None,
    error_summary: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Finish a task record exactly once."""
    if status not in TERMINAL_TASK_STATUSES:
        raise ValueError(f"Invalid terminal task status: {status}")
    with get_db_context() as db:
        task = db.get(IngestionTaskRunORM, task_run_id)
        if task is None:
            raise ValueError(f"Unknown ingestion task run: {task_run_id}")
        if task.status != "running":
            raise ValueError(f"Ingestion task {task_run_id} is already {task.status}")
        task.status = status
        task.finished_at = _utc_now()
        task.rows_read = rows_read
        task.rows_written = rows_written if rows_written is not None else infer_row_count(result)
        task.error_class = type(error).__name__ if error else None
        task.error_summary = _bounded(error_summary or (str(error) if error else None))
        if details is not None:
            task.details = details


def run_has_failed_tasks(run_id: str) -> bool:
    """Return whether any recorded task in a run failed."""
    with get_db_context() as db:
        return (
            db.query(IngestionTaskRunORM)
            .filter(
                IngestionTaskRunORM.run_id == run_id,
                IngestionTaskRunORM.status == "failed",
            )
            .first()
            is not None
        )


class IngestionRunTracker:
    """Own one ingestion run and its session-level advisory lock."""

    def __init__(
        self,
        *,
        run_type: str,
        source: str,
        season: Optional[str],
        target_date: Optional[date],
        season_type: Optional[str] = None,
        feature_cutoff: Optional[datetime] = None,
        provider: Optional[str] = None,
        code_version: Optional[str] = None,
        calculation_version: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        lock_name: str = PIPELINE_LOCK_NAME,
    ):
        self.run_id = str(uuid.uuid4())
        self.run_type = run_type
        self.source = source
        self.season = normalize_season(season) if season else None
        self.season_type = normalize_season_type(season_type) if season_type else None
        self.target_date = target_date
        self.feature_cutoff = feature_cutoff
        self.provider = provider
        self.code_version = code_version or _detect_code_version()
        self.calculation_version = calculation_version
        self.parent_run_id = parent_run_id
        self.details = details
        self.lock_name = lock_name
        self._lock_connection: Optional[Connection] = None
        self._finished = False

    def __enter__(self) -> "IngestionRunTracker":
        self._lock_connection = engine.connect()
        try:
            acquired = bool(
                self._lock_connection.execute(
                    text("SELECT pg_try_advisory_lock(hashtext(:lock_name))"),
                    {"lock_name": self.lock_name},
                ).scalar_one()
            )
            self._lock_connection.commit()
        except Exception:
            self._lock_connection.close()
            self._lock_connection = None
            raise
        if not acquired:
            self._lock_connection.close()
            self._lock_connection = None
            raise IngestionRunAlreadyActive(
                f"Another NBA ingestion pipeline holds lock {self.lock_name!r}"
            )

        try:
            with get_db_context() as db:
                db.add(
                    IngestionRunORM(
                        run_id=self.run_id,
                        parent_run_id=self.parent_run_id,
                        run_type=self.run_type,
                        source=self.source,
                        season=self.season,
                        season_type=self.season_type,
                        target_date=self.target_date,
                        feature_cutoff=self.feature_cutoff,
                        status="running",
                        validation_status="not_run",
                        provider=self.provider,
                        code_version=self.code_version,
                        calculation_version=self.calculation_version,
                        details=self.details,
                    )
                )
        except Exception:
            self._release_lock()
            raise
        return self

    def finish(
        self,
        status: str,
        *,
        validation_status: str = "not_run",
        rows_read: Optional[int] = None,
        rows_written: Optional[int] = None,
        error: Optional[BaseException] = None,
        error_summary: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Set the terminal status for the run."""
        if status not in TERMINAL_RUN_STATUSES:
            raise ValueError(f"Invalid terminal ingestion run status: {status}")
        if validation_status not in {"not_run", "passed", "failed", "skipped"}:
            raise ValueError(f"Invalid validation status: {validation_status}")
        with get_db_context() as db:
            run = db.get(IngestionRunORM, self.run_id)
            if run is None:
                raise ValueError(f"Unknown ingestion run: {self.run_id}")
            if run.status != "running":
                raise ValueError(f"Ingestion run {self.run_id} is already {run.status}")
            run.status = status
            run.validation_status = validation_status
            run.finished_at = _utc_now()
            run.rows_read = rows_read
            run.rows_written = rows_written
            run.error_class = type(error).__name__ if error else None
            run.error_summary = _bounded(error_summary or (str(error) if error else None))
            if details is not None:
                run.details = details
        self._finished = True

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        try:
            if not self._finished:
                if exc_value is not None:
                    self.finish(
                        "failed",
                        validation_status="not_run",
                        error=exc_value,
                    )
                else:
                    self.finish(
                        "failed",
                        validation_status="not_run",
                        error_summary="Run exited without a terminal status",
                    )
        finally:
            self._release_lock()
        return False

    def _release_lock(self) -> None:
        if self._lock_connection is None:
            return
        try:
            self._lock_connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:lock_name))"),
                {"lock_name": self.lock_name},
            )
            self._lock_connection.commit()
        finally:
            self._lock_connection.close()
            self._lock_connection = None
