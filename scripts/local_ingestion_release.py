"""Pin personal-PC ingestion to an explicitly approved, clean Git release."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_FILE = "approved-ingestion-release.json"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True,
                            capture_output=True, text=True, timeout=15)
    return result.stdout.strip()


def release_state(root: Path) -> dict:
    branch = _git(root, "branch", "--show-current")
    if not branch:
        raise ValueError("Ingestion requires a named release branch")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Tracked files changed; ingestion release is not clean")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    for name in filter(None, untracked.split("\0")):
        path = Path(name)
        if path.suffix in {".py", ".ps1"} and (len(path.parts) == 1 or path.parts[0] in {"app", "scripts"}):
            raise ValueError("Untracked application or collection code requires review")
    return {"branch": branch, "commit": _git(root, "rev-parse", "HEAD")}


def verify_release(root: Path, state_dir: Path) -> dict:
    try:
        approved = json.loads((state_dir / APPROVAL_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("No valid approved ingestion release; approve a verified commit first") from exc
    current = release_state(root)
    if any(current[key] != approved.get(key) for key in ("branch", "commit")):
        raise ValueError("Checkout differs from the approved ingestion branch/commit")
    return current


def approve_release(root: Path, state_dir: Path, *, branch: str, commit: str) -> dict:
    current = release_state(root)
    if current != {"branch": branch, "commit": commit}:
        raise ValueError("Approval requires the exact checked-out branch and full commit")
    payload = {**current, "approved_at": datetime.now(timezone.utc).isoformat()}
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / APPROVAL_FILE
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(target)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--branch")
    parser.add_argument("--commit")
    args = parser.parse_args()
    if args.approve and not (args.branch and args.commit):
        parser.error("--approve requires --branch and the full --commit")
    try:
        result = (approve_release(ROOT, args.state_dir, branch=args.branch, commit=args.commit)
                  if args.approve else verify_release(ROOT, args.state_dir))
    except (ValueError, subprocess.SubprocessError) as exc:
        print(f"Release check failed: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
