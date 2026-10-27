"""Credential-safe custom-format backup for the personal-PC database only."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prune_owned_backups(directory: Path, keep: int = 14) -> None:
    """Retain the latest 14 manifests created by this helper only.

    Never traverse links, prune legacy/manual backups, or trust a manifest's
    file field as a deletion target. Require the exact sibling name and hash.
    """
    root = directory.resolve()
    owned = []
    for metadata in root.glob("yunoball_local_*.json"):
        if metadata.is_symlink() or not re.fullmatch(r"yunoball_local_\d{8}\.json", metadata.name):
            continue
        try:
            record = json.loads(metadata.read_text(encoding="utf-8"))
            dump = metadata.with_suffix(".dump")
            if (record.get("format") == "yunoball-local-backup-v1"
                    and not dump.is_symlink() and dump.is_file()
                    and dump.resolve().parent == root
                    and Path(record.get("file", "")).resolve() == dump.resolve()):
                owned.append((metadata, dump, record))
        except (OSError, ValueError):
            continue
    for metadata, dump, record in sorted(owned, key=lambda item: item[0].name, reverse=True)[keep:]:
        if hashlib.sha256(dump.read_bytes()).hexdigest() == record.get("sha256"):
            dump.unlink()
            metadata.unlink()


def backup_database(output_dir: Path, pg_bin: Path) -> dict:
    from dotenv import load_dotenv
    from sqlalchemy.engine import make_url
    from app.utils.local_database_policy import is_local_automation_database

    load_dotenv(ROOT / ".env")
    url = make_url(os.environ["DATABASE_URL"])
    if not is_local_automation_database(url, os.environ):
        raise ValueError("This backup command accepts only the local yunoball_local database")
    output_dir = output_dir.resolve()
    if output_dir == ROOT or ROOT in output_dir.parents:
        raise ValueError("Backups must live outside the repository")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    dump = output_dir / f"yunoball_local_{stamp}.dump"
    manifest = dump.with_suffix(".json")
    if dump.exists() and manifest.exists():
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        try:
            created = datetime.fromisoformat(previous["created_at"].replace("Z", "+00:00"))
            matching_date = (created.tzinfo is not None and
                             created.astimezone(ZoneInfo("America/New_York")).strftime("%Y%m%d") == stamp)
        except (KeyError, TypeError, ValueError):
            matching_date = False
        if (previous.get("format") == "yunoball-local-backup-v1"
                and matching_date
                and previous.get("sha256") == hashlib.sha256(dump.read_bytes()).hexdigest()):
            return previous
        raise ValueError("Existing daily backup failed its Eastern-date, manifest, or hash check; preserve it for inspection")
    if dump.exists() or manifest.exists():
        raise ValueError("Incomplete existing backup needs inspection before replacement")
    temporary = dump.with_suffix(f".dump.partial.{uuid.uuid4().hex}")
    env = os.environ.copy()
    for key, value in {"PGHOST": url.host, "PGPORT": str(url.port or 5432),
                       "PGDATABASE": url.database, "PGUSER": url.username,
                       "PGPASSWORD": url.password}.items():
        if value is not None:
            env[key] = value
    # Connection credentials stay in the child environment, never arguments/logs.
    result = subprocess.run([str(pg_bin / "pg_dump.exe"), "--format=custom",
                             "--file", str(temporary)], env=env, capture_output=True,
                            text=True, timeout=900)
    if result.returncode or not temporary.exists() or temporary.stat().st_size == 0:
        raise RuntimeError("pg_dump failed; no successful backup was published")
    listing = subprocess.run([str(pg_bin / "pg_restore.exe"), "--list", str(temporary)],
                             capture_output=True, text=True, timeout=60)
    if listing.returncode or not listing.stdout.strip():
        raise RuntimeError("pg_restore archive listing failed")
    report = {"format": "yunoball-local-backup-v1", "database": url.database,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "file": str(dump), "bytes": temporary.stat().st_size,
              "sha256": hashlib.sha256(temporary.read_bytes()).hexdigest(),
              "archive_listing_verified": True, "restore_tested": False}
    temporary.replace(dump)
    staged = manifest.with_suffix(".json.partial")
    staged.write_text(json.dumps(report, indent=2), encoding="utf-8")
    staged.replace(manifest)
    prune_owned_backups(output_dir)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pg-bin", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(backup_database(args.output_dir, args.pg_bin), indent=2))
        return 0
    except Exception as exc:
        # Do not print exception values that might contain credentials/URLs.
        print(f"Local backup failed ({type(exc).__name__}); inspect backup files and database availability", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
