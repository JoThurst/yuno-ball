"""Once-per-Eastern-date local ingestion with restart-safe status and a backup gate."""
from __future__ import annotations

import argparse
from datetime import datetime, time, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EASTERN = ZoneInfo("America/New_York")
CYCLE_LOCK = "yunoball:local_daily_cycle"


def cycle_due(now: datetime, last_success_date: str | None) -> bool:
    local = now.astimezone(EASTERN)
    return local.hour >= 8 and last_success_date != local.date().isoformat()


def publish_status(path: Path, state: str, **details) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + f".{os.getpid()}.tmp")
    staged.write_text(json.dumps({"state": state,
        "updated_at": datetime.now(timezone.utc).isoformat(), **details}, indent=2, default=str), encoding="utf-8")
    staged.replace(path)


def latest_success_date(connection) -> str | None:
    from sqlalchemy import text
    value = connection.execute(text("""SELECT max(target_date) FROM ingestion_runs
        WHERE run_type='local_daily_cycle' AND status='success' AND validation_status='passed'""")).scalar_one()
    return value.isoformat() if value else None


def validated_daily_exists(connection, target) -> bool:
    from sqlalchemy import text
    from daily_ingest import FETCH_TASKS, CALC_TASKS

    since = datetime.combine(target, time(8), EASTERN).astimezone(timezone.utc)
    candidates = connection.execute(text("""SELECT details FROM ingestion_runs
        WHERE run_type='daily_ingest' AND status='success' AND validation_status='passed'
        AND target_date=:day AND started_at>=:since
        AND coalesce((details->>'calc_only')::boolean,false)=false
        AND coalesce((details->>'validate_only')::boolean,false)=false
        AND coalesce((details->>'fetch_only')::boolean,false)=false"""),
        {"day": target, "since": since}).scalars()
    return any(full_daily_scope(details, FETCH_TASKS, CALC_TASKS) for details in candidates)


def full_daily_scope(details: dict, fetch_tasks: list, calc_tasks: list) -> bool:
    """A successful selected-task run is not a checkpoint for the whole cycle."""
    if not isinstance(details, dict):
        return False
    fetched, calculated = details.get("fetch_tasks"), details.get("calc_tasks")
    if not isinstance(fetched, list) or not isinstance(calculated, list):
        return False
    return (all(task in fetched for task in fetch_tasks if task != "injury")
            and all(task in calculated for task in calc_tasks))


def build_commands(args, daily_already_passed: bool) -> list:
    commands = [["scripts/backup_local_database.py", "--output-dir",
                 str(args.state_dir / "backups"), "--pg-bin", str(args.pg_bin)]]
    if args.force or not daily_already_passed:
        commands.append(["daily_ingest.py", "--local", "--exclude-fetch", "injury"])
    commands.append(["scripts/run_official_injury_pipeline.py", "--archive-root", str(args.archive_root)])
    return commands


def run(args) -> int:
    from sqlalchemy import text
    from app.database import engine
    from app.services.ingestion_run_service import IngestionRunAlreadyActive, IngestionRunTracker
    from app.utils.local_database_policy import is_local_automation_database

    now = datetime.now(timezone.utc)
    target = now.astimezone(EASTERN).date()
    if not args.force and now.astimezone(EASTERN).hour < 8:
        print("Before 08:00 Eastern; no ingestion due")
        return 0
    if not is_local_automation_database(engine.url, os.environ):
        raise ValueError("The PC scheduler requires the local yunoball_local database")
    with engine.connect() as connection:
        if connection.execute(text("select current_database()")).scalar_one() != "yunoball_local":
            raise ValueError("The PC scheduler is restricted to yunoball_local")
        last = latest_success_date(connection)
    if not args.force and not cycle_due(now, last):
        print("Today's complete local cycle already passed; skipping")
        return 0
    if args.check_only:
        print(json.dumps({"due": True, "target_date": str(target), "last_success": last}))
        return 0
    status_file = args.state_dir / "ingestion-status.json"
    try:
        with IngestionRunTracker(run_type="local_daily_cycle", source="pc_scheduler",
                season=None, target_date=target, provider="local_pc",
                lock_name=CYCLE_LOCK,
                details={"network": "direct", "mode": "backup_then_daily_then_official_injury",
                         "code_release": getattr(args, "code_release", None)}) as tracker:
            # Recheck after owning the controller lock; a competing trigger may
            # have just finished while this invocation was waiting to start.
            with engine.connect() as connection:
                if not args.force and not cycle_due(now, latest_success_date(connection)):
                    tracker.finish("success", validation_status="passed", details={"no_op": True})
                    return 0
            publish_status(status_file, "running", run_id=tracker.run_id, target_date=target)
            with engine.connect() as connection:
                daily_already_passed = validated_daily_exists(connection, target)
            commands = build_commands(args, daily_already_passed)
            if daily_already_passed and not args.force:
                print("Today's full daily stats already validated; retrying remaining phases only", flush=True)
            env = os.environ.copy()
            env.update(FORCE_LOCAL="true", FORCE_PROXY="false", PROXY_ENABLED="false", MAX_WORKERS="1")
            for command in commands:
                publish_status(status_file, "running", run_id=tracker.run_id,
                               target_date=target, phase=command[0])
                # Children own the normal daily lock. The separate cycle lock
                # prevents duplicate controllers without bypassing writer gates.
                code = run_child([sys.executable, *command], env=env)
                if code:
                    tracker.finish("failed", validation_status="failed",
                                   error_summary=f"{command[0]} exited {code}")
                    publish_status(status_file, "deferred" if code == 3 else "failed",
                                   run_id=tracker.run_id, target_date=target, phase=command[0],
                                   exit_code=code, retry="09:30 Eastern or next hourly availability check")
                    return code
            # Exit zero alone does not prove a complete daily fetch: the daily
            # orchestrator can exit zero with noncritical failed tasks.
            with engine.connect() as connection:
                passed = validated_daily_exists(connection, target)
            if not passed:
                raise RuntimeError("No complete validated daily run for this cycle")
            tracker.finish("success", validation_status="passed")
            publish_status(status_file, "success", run_id=tracker.run_id, target_date=target,
                           code_release=getattr(args, "code_release", None))
            return 0
    except IngestionRunAlreadyActive:
        print("Another local cycle is active; the existing owner continues")
        return 3
    except Exception as exc:
        publish_status(status_file, "failed", target_date=target, error_class=type(exc).__name__,
                       retry="09:30 Eastern or next hourly availability check")
        print(f"Local cycle failed ({type(exc).__name__}); see ingestion-status.json", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="Supervised retry even if already successful")
    args = parser.parse_args(argv)
    from scripts.local_ingestion_release import verify_release
    try:
        args.code_release = verify_release(ROOT, args.state_dir)
    except (ValueError, subprocess.SubprocessError) as exc:
        publish_status(args.state_dir / "ingestion-status.json", "failed",
                       error_class=type(exc).__name__, phase="preflight", error_summary=str(exc))
        print(f"Local release preflight failed: {exc}", file=sys.stderr)
        return 1
    try:
        return run(args)
    except Exception as exc:
        publish_status(args.state_dir / "ingestion-status.json", "failed",
                       error_class=type(exc).__name__, phase="preflight")
        print(f"Local cycle preflight failed ({type(exc).__name__}); see status file", file=sys.stderr)
        return 1


def run_child(command: list, *, env: dict, timeout: int = 3600) -> int:
    process = subprocess.Popen(command, cwd=ROOT, env=env)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Windows venv launchers own another python.exe; terminate the exact
        # child tree so an orphan writer cannot retain the shared daily lock.
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, check=False, timeout=30)
        else:
            process.kill()
        process.wait(timeout=30)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
