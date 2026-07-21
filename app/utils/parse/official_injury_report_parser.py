"""Parse official NBA injury-report PDFs into source-preserving observations.

This module intentionally stops at parsed source observations. It does not
resolve NBA IDs, infer availability, or write database rows. The PDF layout
uses stable visual columns, so parsing is based on ``pdfplumber``'s
layout-preserving text rather than whitespace-collapsed text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import re
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


EASTERN = ZoneInfo("America/New_York")
PARSER_VERSION = "official-injury-report-layout-v1"

_REPORT_HEADER = re.compile(
    r"Injury\s+Report:\s+(?P<date>\d{2}/\d{2}/\d{2})\s+"
    r"(?P<time>\d{1,2}:\d{2})\s+(?P<meridiem>AM|PM)",
    re.IGNORECASE,
)
_GAME_DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
_GAME_TIME = re.compile(r"\d{1,2}:\d{2}\s+\(ET\)")
_MATCHUP = re.compile(r"\b[A-Z]{3}@[A-Z]{3}\b")
_STATUS_VALUES = {
    "AVAILABLE": "Available",
    "PROBABLE": "Probable",
    "QUESTIONABLE": "Questionable",
    "DOUBTFUL": "Doubtful",
    "OUT": "Out",
}
_NOT_SUBMITTED = "NOT YET SUBMITTED"


@dataclass(frozen=True)
class ParsedAvailabilityObservation:
    """One player status exactly as reported in one official document."""

    game_date: date
    game_time: Optional[time]
    game_time_text: Optional[str]
    matchup: str
    reported_team_name: str
    reported_player_name: str
    current_status: str
    raw_reason: Optional[str]
    reason_category: Optional[str]
    reason_detail: Optional[str]


@dataclass(frozen=True)
class ParsedTeamSubmissionStatus:
    """One explicit team submission state from an official document."""

    game_date: date
    game_time: Optional[time]
    game_time_text: Optional[str]
    matchup: str
    reported_team_name: str
    submission_status: str
    raw_text: str


@dataclass(frozen=True)
class OfficialInjuryReportParseResult:
    """Parsed report payload before identity resolution or persistence."""

    report_published_at: datetime
    observations: Tuple[ParsedAvailabilityObservation, ...]
    team_submission_statuses: Tuple[ParsedTeamSubmissionStatus, ...]
    page_count: int
    parse_status: str
    parse_error_summary: Optional[str]


@dataclass
class _GameContext:
    game_date: Optional[date] = None
    game_time: Optional[time] = None
    game_time_text: Optional[str] = None
    matchup: Optional[str] = None
    team_name: Optional[str] = None


@dataclass
class _Row:
    line_index: int
    context: _GameContext
    player_name: str
    status: str
    reason_parts: List[Tuple[int, str]]


def _clean(value: str) -> str:
    return " ".join(value.split()).strip()


def _parse_report_timestamp(text: str) -> datetime:
    match = _REPORT_HEADER.search(text)
    if match is None:
        raise ValueError("Official report timestamp was not found")
    parsed = datetime.strptime(
        f"{match.group('date')} {match.group('time')} {match.group('meridiem')}",
        "%m/%d/%y %I:%M %p",
    )
    return parsed.replace(tzinfo=EASTERN)


def _status_match(line: str) -> Tuple[Optional[str], Optional[int]]:
    upper = line.upper()
    if _NOT_SUBMITTED in upper:
        return _NOT_SUBMITTED, None
    # ``Questionable`` can touch the reason column in layout text even though
    # the PDF's visual columns remain separate. Keep the search bounded so a
    # reason word cannot become a status, but do not truncate the status token.
    status_column = line[75:100]
    for raw, normalized in _STATUS_VALUES.items():
        match = re.search(rf"(?<![A-Z]){raw}(?![A-Z])", status_column.upper())
        if match:
            return normalized, 75 + match.end()
    return None, None


def _parse_game_date(line: str, fallback: Optional[date]) -> Optional[date]:
    match = _GAME_DATE.search(line[:28])
    if match is None:
        return fallback
    return datetime.strptime(match.group(), "%m/%d/%Y").date()


def _parse_game_time(line: str, fallback: Optional[time]) -> Optional[time]:
    match = _GAME_TIME.search(line[:28])
    if match is None:
        return fallback
    return time.fromisoformat(match.group().split()[0])


def _parse_game_time_text(line: str, fallback: Optional[str]) -> Optional[str]:
    match = _GAME_TIME.search(line[:28])
    if match is None:
        return fallback
    return _clean(match.group())


def _reason_fields(raw_reason: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not raw_reason or raw_reason == "-":
        return None, None
    if " - " in raw_reason:
        category, detail = raw_reason.split(" - ", 1)
        return category.strip() or None, detail.strip() or None
    return raw_reason, None


def _page_rows(
    page_text: str,
    *,
    context: _GameContext,
) -> Tuple[List[ParsedAvailabilityObservation], List[ParsedTeamSubmissionStatus]]:
    """Parse one layout-preserved page and carry game/team context forward."""
    rows: List[_Row] = []
    submissions: List[ParsedTeamSubmissionStatus] = []
    continuation_lines: List[Tuple[int, str]] = []

    for line_index, line in enumerate(page_text.splitlines()):
        stripped = _clean(line)
        if not stripped:
            continue
        if _REPORT_HEADER.search(line) or stripped.startswith("Game Date"):
            continue
        if re.fullmatch(r"Page\s+\d+\s+of\s+\d+", stripped, re.IGNORECASE):
            continue

        matchup_match = _MATCHUP.search(line)
        if matchup_match:
            context.game_date = _parse_game_date(line, context.game_date)
            context.game_time = _parse_game_time(line, context.game_time)
            context.game_time_text = _parse_game_time_text(
                line,
                context.game_time_text,
            )
            context.matchup = matchup_match.group()
            team = _clean(line[36:59])
            if team:
                context.team_name = team
        elif _GAME_DATE.search(line[:28]):
            context.game_date = _parse_game_date(line, context.game_date)
            context.game_time = _parse_game_time(line, context.game_time)
            context.game_time_text = _parse_game_time_text(
                line,
                context.game_time_text,
            )

        team = _clean(line[36:59])
        if team:
            context.team_name = team

        status, status_end = _status_match(line)
        player_name = _clean(line[59:81])
        # A same-line reason begins after the full status column. Wrapped
        # continuation lines are visually shifted a few characters left.
        reason = _clean(
            line[status_end:] if player_name and status_end is not None else line[92:]
        )

        if status == _NOT_SUBMITTED and not player_name:
            if context.game_date and context.matchup and context.team_name:
                submissions.append(
                    ParsedTeamSubmissionStatus(
                        game_date=context.game_date,
                        game_time=context.game_time,
                        game_time_text=context.game_time_text,
                        matchup=context.matchup,
                        reported_team_name=context.team_name,
                        submission_status=_NOT_SUBMITTED,
                        raw_text=stripped,
                    )
                )
            continue

        if player_name and status in _STATUS_VALUES.values():
            if not context.game_date or not context.matchup or not context.team_name:
                continue
            rows.append(
                _Row(
                    line_index=line_index,
                    context=_GameContext(
                        game_date=context.game_date,
                        game_time=context.game_time,
                        game_time_text=context.game_time_text,
                        matchup=context.matchup,
                        team_name=context.team_name,
                    ),
                    player_name=player_name,
                    status=status,
                    reason_parts=[(line_index, reason)] if reason else [],
                )
            )
            continue

        if reason and not player_name and not matchup_match:
            continuation_lines.append((line_index, reason))

    for line_index, reason in continuation_lines:
        if not rows:
            continue
        nearest = min(rows, key=lambda row: abs(row.line_index - line_index))
        nearest.reason_parts.append((line_index, reason))

    observations: List[ParsedAvailabilityObservation] = []
    for row in rows:
        raw_reason = _clean(" ".join(reason for _, reason in sorted(row.reason_parts)))
        if not raw_reason:
            raw_reason = None
        category, detail = _reason_fields(raw_reason)
        observations.append(
            ParsedAvailabilityObservation(
                game_date=row.context.game_date,  # type: ignore[arg-type]
                game_time=row.context.game_time,
                game_time_text=row.context.game_time_text,
                matchup=row.context.matchup,  # type: ignore[arg-type]
                reported_team_name=row.context.team_name,  # type: ignore[arg-type]
                reported_player_name=row.player_name,
                current_status=row.status,
                raw_reason=raw_reason,
                reason_category=category,
                reason_detail=detail,
            )
        )
    return observations, submissions


def parse_official_injury_report_layout(
    page_texts: Sequence[str],
    *,
    report_published_at: Optional[datetime] = None,
) -> OfficialInjuryReportParseResult:
    """Parse layout-preserved page text for deterministic unit testing."""
    combined = "\n".join(page_texts)
    published_at = report_published_at or _parse_report_timestamp(combined)
    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("report_published_at must be timezone-aware")

    context = _GameContext()
    observations: List[ParsedAvailabilityObservation] = []
    submissions: List[ParsedTeamSubmissionStatus] = []
    for page_text in page_texts:
        page_observations, page_submissions = _page_rows(
            page_text,
            context=context,
        )
        observations.extend(page_observations)
        submissions.extend(page_submissions)

    status = "parsed" if observations or submissions else "failed"
    error = None if status == "parsed" else "No player or team rows were parsed"
    return OfficialInjuryReportParseResult(
        report_published_at=published_at.astimezone(EASTERN),
        observations=tuple(observations),
        team_submission_statuses=tuple(submissions),
        page_count=len(page_texts),
        parse_status=status,
        parse_error_summary=error,
    )


def parse_official_injury_report_pdf(path: str | Path) -> OfficialInjuryReportParseResult:
    """Extract and parse an official PDF without changing or storing the file."""
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - environment failure path
        raise RuntimeError(
            "pdfplumber is required to parse official injury-report PDFs"
        ) from exc

    with pdfplumber.open(path) as document:
        page_texts = [
            page.extract_text(layout=True, x_tolerance=1, y_tolerance=3) or ""
            for page in document.pages
        ]
    return parse_official_injury_report_layout(page_texts)
