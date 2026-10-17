"""Read-only, bounded smoke checks for a deployed Yuno Ball staging URL."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

import requests


PRODUCTION_404_PATHS = ("/dashboard/", "/design/status", "/design/daily-v1", "/daily/betting")


class ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]

    def json(self) -> Any: ...


class Transport(Protocol):
    def get(self, path: str, *, allow_redirects: bool = True) -> ResponseLike: ...


@dataclass(frozen=True)
class MatchupSpec:
    date: str
    away: str
    home: str

    @classmethod
    def parse(cls, raw: str) -> "MatchupSpec":
        parts = raw.strip().split("/")
        if len(parts) != 2:
            raise ValueError("matchup must use YYYY-MM-DD/AWAY-HOME")
        target_date, teams = parts
        team_parts = teams.upper().split("-")
        if len(team_parts) != 2 or not all(team.isalpha() for team in team_parts):
            raise ValueError("matchup must use YYYY-MM-DD/AWAY-HOME")
        _parse_date(target_date)
        return cls(target_date, team_parts[0], team_parts[1])

    @property
    def path(self) -> str:
        return f"/matchup/{self.date}/{self.away}-{self.home}"


@dataclass
class Check:
    name: str
    path: str
    expected: str
    observed: str
    passed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "expected": self.expected,
            "observed": self.observed,
            "status": "PASS" if self.passed else "FAIL",
        }


def _parse_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"invalid date: {value}") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(f"invalid date: {value}")
    return value


def _validate_base_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain credentials, query, or fragment")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("localhost is not accepted as staging evidence")
    return raw.rstrip("/")


class RequestsTransport:
    def __init__(self, base_url: str, timeout: float) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "yunoball-staging-smoke/1"})

    def get(self, path: str, *, allow_redirects: bool = True) -> ResponseLike:
        return self._session.get(
            f"{self._base_url}{path}", timeout=self._timeout, allow_redirects=allow_redirects
        )


def _commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _query_path(path: str, query: Mapping[str, str]) -> str:
    return f"{path}?{urlencode(query)}" if query else path


def _check_status(checks: list[Check], name: str, path: str, response: ResponseLike, expected: int) -> None:
    checks.append(Check(name, path, str(expected), str(response.status_code), response.status_code == expected))


def _daily_payload(response: ResponseLike, path: str, checks: list[Check]) -> Optional[dict[str, Any]]:
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except (ValueError, TypeError):
        checks.append(Check("daily JSON", path, "valid JSON object", "invalid JSON", False))
        return None
    if not isinstance(payload, dict):
        checks.append(Check("daily JSON", path, "JSON object", type(payload).__name__, False))
        return None
    return payload


def _games(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = payload.get("games")
    return [game for game in value if isinstance(game, Mapping)] if isinstance(value, list) else []


def _find_game(payload: Mapping[str, Any], spec: MatchupSpec) -> Optional[Mapping[str, Any]]:
    for game in _games(payload):
        away = game.get("away") or {}
        home = game.get("home") or {}
        if str(away.get("abbreviation", "")).upper() == spec.away and str(home.get("abbreviation", "")).upper() == spec.home:
            return game
    return None


def run_smoke(
    transport: Transport,
    *,
    dates: Iterable[str],
    scheduled: MatchupSpec,
    final: MatchupSpec,
    empty_date: str,
    stale_date: str,
    season: Optional[str] = None,
    readiness_expected: Optional[str] = None,
) -> list[Check]:
    checks: list[Check] = []
    date_values = list(dates)
    date_payloads: dict[str, dict[str, Any]] = {}
    date_query = {"season": season} if season else {}

    for target_date in date_values:
        path = _query_path("/daily/api/v1", {"date": target_date, **date_query})
        try:
            response = transport.get(path)
        except Exception as exc:
            checks.append(Check("real date request", path, "HTTP 200", f"transport error: {type(exc).__name__}", False))
            continue
        _check_status(checks, "real date request", path, response, 200)
        payload = _daily_payload(response, path, checks)
        if payload is None:
            continue
        date_payloads[target_date] = payload
        observed_date = str(payload.get("target_date", "missing"))
        checks.append(Check("date assertion", path, target_date, observed_date, observed_date == target_date))
        game_count = len(_games(payload))
        checks.append(Check("real date has games", path, "> 0 games", str(game_count), game_count > 0))

    for spec, expected_state in ((scheduled, "scheduled"), (final, "final")):
        payload = date_payloads.get(spec.date)
        game = _find_game(payload, spec) if payload else None
        observed = str(game.get("state", "missing")) if game else "missing"
        checks.append(Check(
            f"{expected_state} matchup identity",
            f"/daily/api/v1?date={spec.date}",
            f"{spec.away}-{spec.home}, state={expected_state}",
            observed,
            game is not None and observed == expected_state,
        ))
        try:
            response = transport.get(spec.path)
            _check_status(checks, f"{expected_state} matchup page", spec.path, response, 200)
        except Exception as exc:
            checks.append(Check(f"{expected_state} matchup page", spec.path, "HTTP 200", f"transport error: {type(exc).__name__}", False))

    archive_path = "/daily/archive"
    try:
        _check_status(checks, "archive", archive_path, transport.get(archive_path), 200)
    except Exception as exc:
        checks.append(Check("archive", archive_path, "HTTP 200", f"transport error: {type(exc).__name__}", False))

    for label, target_date in (("empty state", empty_date), ("stale state", stale_date)):
        path = _query_path("/daily/api/v1", {"date": target_date, **date_query})
        try:
            response = transport.get(path)
            _check_status(checks, label, path, response, 200)
            payload = _daily_payload(response, path, checks)
            if payload is not None and label == "empty state":
                observed = str(payload.get("status", "missing"))
                checks.append(Check(label, path, "status=empty and zero games", f"status={observed}, games={len(_games(payload))}", observed == "empty" and not _games(payload)))
            elif payload is not None:
                freshness = payload.get("freshness") or {}
                observed = str(freshness.get("status", "missing"))
                checks.append(Check(label, path, "freshness.status=stale", observed, observed == "stale" or bool(freshness.get("is_stale"))))
        except Exception as exc:
            checks.append(Check(label, path, "controlled staging response", f"transport error: {type(exc).__name__}", False))

    redirect_date = date_values[0]
    redirect_query = {"date": redirect_date, **date_query}
    for label, path in (("daily date redirect", _query_path("/daily/", redirect_query)), ("home date redirect", _query_path("/home", redirect_query))):
        try:
            response = transport.get(path, allow_redirects=False)
            location = str(response.headers.get("Location", ""))
            parsed = urlparse(location)
            expected_path = f"/daily/{redirect_date}"
            query_ok = not season or parse_qs(parsed.query).get("season") == [season]
            checks.append(Check(label, path, f"302 Location={expected_path}", f"{response.status_code} Location={parsed.path or 'missing'}", response.status_code == 302 and parsed.path == expected_path and query_ok))
        except Exception as exc:
            checks.append(Check(label, path, "302 redirect", f"transport error: {type(exc).__name__}", False))

    for path in PRODUCTION_404_PATHS:
        try:
            _check_status(checks, "production route restriction", path, transport.get(path), 404)
        except Exception as exc:
            checks.append(Check("production route restriction", path, "HTTP 404", f"transport error: {type(exc).__name__}", False))

    readiness_path = "/health/ready"
    try:
        response = transport.get(readiness_path)
        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = {}
        observed = str(payload.get("status", "invalid")) if isinstance(payload, dict) else "invalid"
        expected_http = {"ready": 200, "degraded_ready": 200, "not_ready": 503}.get(observed)
        checks.append(Check("readiness HTTP/state", readiness_path, "ready=200, degraded_ready=200, not_ready=503", f"HTTP {response.status_code}, state={observed}", expected_http == response.status_code))
        if readiness_expected:
            checks.append(Check("readiness controlled expectation", readiness_path, readiness_expected, observed, readiness_expected == observed))
    except Exception as exc:
        checks.append(Check("readiness HTTP/state", readiness_path, "readiness JSON", f"transport error: {type(exc).__name__}", False))

    return checks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Explicit staging base URL; localhost is rejected")
    parser.add_argument("--date", action="append", required=True, help="One real non-empty staging date; repeat exactly twice")
    parser.add_argument("--scheduled-matchup", required=True, help="YYYY-MM-DD/AWAY-HOME present as scheduled")
    parser.add_argument("--final-matchup", required=True, help="YYYY-MM-DD/AWAY-HOME present as final")
    parser.add_argument("--empty-date", required=True, help="Controlled staging date whose Daily payload is empty")
    parser.add_argument("--stale-date", required=True, help="Controlled staging date whose Daily payload is stale")
    parser.add_argument("--season", help="Optional season query passed to Daily endpoints")
    parser.add_argument("--readiness-expected", choices=("ready", "degraded_ready", "not_ready"), help="Optional state assertion for a controlled readiness run")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-request timeout in seconds (default: 15)")
    return parser


def main(argv: Optional[list[str]] = None, *, transport_factory: Callable[[str, float], Transport] = RequestsTransport) -> int:
    args = _parser().parse_args(argv)
    try:
        base_url = _validate_base_url(args.base_url)
        dates = [_parse_date(value) for value in args.date]
        if len(dates) != 2 or len(set(dates)) != 2:
            raise ValueError("--date must be supplied exactly twice with distinct dates")
        scheduled = MatchupSpec.parse(args.scheduled_matchup)
        final = MatchupSpec.parse(args.final_matchup)
        empty_date = _parse_date(args.empty_date)
        stale_date = _parse_date(args.stale_date)
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        if scheduled.date not in dates or final.date not in dates:
            raise ValueError("scheduled and final matchup dates must be the two --date values")
        checks = run_smoke(transport_factory(base_url, args.timeout), dates=dates, scheduled=scheduled, final=final, empty_date=empty_date, stale_date=stale_date, season=args.season, readiness_expected=args.readiness_expected)
    except (ValueError, requests.RequestException) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 2

    passed = all(check.passed for check in checks)
    evidence = {
        "status": "PASS" if passed else "FAIL",
        "commit": _commit(),
        "environment": urlparse(base_url).hostname or "unknown",
        "utc_time": datetime.now(timezone.utc).isoformat(),
        "checks": [check.as_dict() for check in checks],
        "limitations": [
            "Read-only HTTP checks only; no ingestion, dependency mutation, or database writes.",
            "The operator supplied dates and state cases; localhost and fixture responses are not accepted as staging evidence.",
            "Readiness states not controlled in this run are observations, not proof of the other states.",
        ],
    }
    print(json.dumps(evidence, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
