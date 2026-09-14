"""Versioned, read-only Daily Intelligence V1 package.

This module is an adapter around the cutoff-safe slate service.  It deliberately
does not fetch live data, persist a new metric, or make a prediction.  The
outer dataclasses are the stable contract; nested source dictionaries preserve
the existing provenance-rich slate details for future consumers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.services.slate_service import build_slate_context


DAILY_INTELLIGENCE_CONTRACT_VERSION = "daily-intelligence-v1"


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json_ready(value: Any) -> Any:
    """Convert legacy template values into JSON-safe values recursively."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _number(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 1) -> Optional[float]:
    number = _number(value)
    return round(number, digits) if number is not None else None


def _status_token(value: Any) -> str:
    return str(value or "").strip().lower()


@dataclass(frozen=True)
class DailyFreshnessV1:
    source: str
    status: str
    completeness: str
    as_of: Optional[str]
    run_id: Optional[str]
    target_date: Optional[str]
    season: Optional[str]
    is_stale: bool
    has_marker: bool
    explanation: str


@dataclass(frozen=True)
class DailyInsightV1:
    insight_id: str
    kind: str
    priority: int
    headline: str
    explanation: str
    game_id: Optional[str] = None
    team_id: Optional[int] = None
    status: str = "available"
    source: str = "derived_from_slate"
    as_of: Optional[str] = None
    completeness: str = "unknown"
    metric_context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DailyGameV1:
    game_id: str
    game_date: Optional[str]
    tipoff: Optional[str]
    state: str
    home: Mapping[str, Any]
    away: Mapping[str, Any]
    matchup_priority: Mapping[str, Any]
    signals: Mapping[str, Any]
    players_to_watch: Sequence[Mapping[str, Any]]
    provenance: Mapping[str, Any]
    market: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class DailyIntelligenceV1:
    contract_version: str
    target_date: str
    season: Optional[str]
    status: str
    freshness: DailyFreshnessV1
    summary: Mapping[str, Any]
    games: Sequence[DailyGameV1]
    insights: Sequence[DailyInsightV1]
    disclaimers: Sequence[str]

    def to_dict(self) -> Dict[str, Any]:
        return _json_ready(asdict(self))


def _freshness(raw: Mapping[str, Any], target_date: date, season: Optional[str]) -> DailyFreshnessV1:
    has_marker = bool(raw.get("has_marker"))
    is_stale = bool(raw.get("is_stale"))
    raw_status = _status_token(raw.get("status"))
    if not has_marker or raw_status in {"", "unknown"}:
        status = "unknown"
        explanation = "No validated ingest marker is available for this package."
    elif is_stale:
        status = "stale"
        explanation = "The latest ingest marker is older than the configured freshness window."
    elif raw.get("is_complete"):
        status = "fresh"
        explanation = "The latest ingest marker reports a validated run."
    else:
        status = "partial"
        explanation = "An ingest marker exists, but it is not fully validated."

    return DailyFreshnessV1(
        source=str(raw.get("source") or "daily_ingest"),
        status=status,
        completeness="complete" if raw.get("is_complete") else ("partial" if has_marker else "unknown"),
        as_of=_iso(raw.get("as_of") or raw.get("timestamp")),
        run_id=raw.get("run_id"),
        target_date=raw.get("target_date") or target_date.isoformat(),
        season=raw.get("season") or season,
        is_stale=is_stale,
        has_marker=has_marker,
        explanation=explanation,
    )


def _availability_summary(raw: Any) -> Dict[str, Any]:
    metadata = raw if isinstance(raw, Mapping) else {}
    observations = metadata.get("observations") if isinstance(raw, Mapping) else raw
    observations = observations if isinstance(observations, list) else []
    counts: Dict[str, int] = {}
    for observation in observations:
        if isinstance(observation, Mapping):
            status = str(observation.get("status") or "unknown").strip().lower()
            counts[status] = counts.get(status, 0) + 1
    unresolved = metadata.get("unresolved_count")
    if unresolved is None:
        unresolved = metadata.get("unresolved_observation_count")
    if unresolved is None and isinstance(raw, list):
        unresolved = sum(
            1
            for observation in observations
            if isinstance(observation, Mapping)
            and observation.get("identity_status") not in (None, "resolved")
        )
    return {
        "source": metadata.get("source"),
        "as_of": _iso(metadata.get("as_of")),
        "completeness": metadata.get("completeness") or metadata.get("completeness_status") or "unknown",
        "status_counts": counts,
        "unresolved_count": unresolved if unresolved is not None else 0,
        "unknown_reason": metadata.get("unknown_reason"),
    }


def _schedule_summary(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {"status": "missing", "flags": []}
    flags = [
        label
        for key, label in (
            ("is_b2b", "back_to_back"),
            ("is_3_in_4", "three_in_four"),
            ("is_4_in_5", "four_in_five"),
            ("is_5_in_7", "five_in_seven"),
        )
        if raw.get(key)
    ]
    return {
        "status": "available",
        "team_id": raw.get("team_id"),
        "days_rest": raw.get("days_rest"),
        "opponent_days_rest": raw.get("opponent_days_rest"),
        "rest_edge": raw.get("rest_edge"),
        "rest_diff": raw.get("rest_diff"),
        "flags": flags,
    }


def _team_form(game: Mapping[str, Any], side: str) -> Dict[str, Any]:
    prefix = "home" if side == "home" else "away"
    return {
        "team_id": game.get(f"{prefix}_team_id"),
        "net_rating_delta": _round(game.get(f"{prefix}_net_delta")),
        "flags": game.get(f"{prefix}_flags") or [],
    }


def _game_priority(game: Mapping[str, Any], home_availability: Mapping[str, Any], away_availability: Mapping[str, Any]) -> Tuple[float, List[str]]:
    """Create an editorial ordering, never a predictive importance score."""
    score = 0.0
    reasons: List[str] = []
    environment = game.get("environment") or {}
    pace = _number(environment.get("pace_projection"))
    scoring = _number(environment.get("scoring_env_index"))
    if pace is not None and abs(pace - 100) >= 2:
        score += 1
        reasons.append("distinctive pace context")
    if scoring is not None and abs(scoring - 100) >= 3:
        score += 1
        reasons.append("distinctive scoring context")

    for side, form in (("home", _team_form(game, "home")), ("away", _team_form(game, "away"))):
        delta = _number(form.get("net_rating_delta"))
        if delta is not None and abs(delta) >= 3:
            score += 1
            reasons.append(f"{side} team form signal")

    for side, availability in (("home", home_availability), ("away", away_availability)):
        counts = availability.get("status_counts") or {}
        unresolved = int(availability.get("unresolved_count") or 0)
        if unresolved or counts.get("out", 0) or counts.get("doubtful", 0) or counts.get("questionable", 0):
            score += 1
            reasons.append(f"{side} availability uncertainty")

    for side in ("home", "away"):
        schedule = _schedule_summary(game.get(f"{side}_schedule"))
        if schedule["flags"]:
            score += 1
            reasons.append(f"{side} schedule pressure")

    if not reasons:
        reasons.append("baseline slate context")
    return min(score, 10.0), reasons


def _insight(
    target_date: date,
    kind: str,
    priority: int,
    headline: str,
    explanation: str,
    *,
    game_id: Optional[str] = None,
    team_id: Optional[int] = None,
    source: str = "derived_from_slate",
    as_of: Optional[str] = None,
    completeness: str = "unknown",
    metric_context: Optional[Mapping[str, Any]] = None,
) -> DailyInsightV1:
    scope = game_id or "slate"
    return DailyInsightV1(
        insight_id=f"di-v1:{target_date.isoformat()}:{scope}:{kind}",
        kind=kind,
        priority=priority,
        headline=headline,
        explanation=explanation,
        game_id=game_id,
        team_id=team_id,
        source=source,
        as_of=as_of,
        completeness=completeness,
        metric_context=metric_context or {},
    )


def _build_game(target_date: date, raw: Mapping[str, Any]) -> Tuple[DailyGameV1, List[DailyInsightV1]]:
    game_id = str(raw.get("game_id"))
    overall_availability = _availability_summary(raw.get("availability") or {})

    def team_availability(side: str) -> Dict[str, Any]:
        summary = _availability_summary(raw.get(f"{side}_availability") or {})
        for key in ("source", "as_of", "completeness", "unknown_reason"):
            if summary.get(key) in (None, "unknown"):
                summary[key] = overall_availability.get(key)
        if not summary.get("unresolved_count"):
            summary["unresolved_count"] = overall_availability.get("unresolved_count") or 0
        return summary

    home_availability = team_availability("home")
    away_availability = team_availability("away")
    priority_score, priority_reasons = _game_priority(raw, home_availability, away_availability)
    state = "completed" if raw.get("result_home") is not None else "scheduled"
    environment = raw.get("environment") or {}
    schedule = {
        "home": _schedule_summary(raw.get("home_schedule")),
        "away": _schedule_summary(raw.get("away_schedule")),
    }
    team_form = {"home": _team_form(raw, "home"), "away": _team_form(raw, "away")}
    availability = {"home": home_availability, "away": away_availability}
    players = list(raw.get("home_players") or []) + list(raw.get("away_players") or [])
    market = raw.get("observed_markets")

    game = DailyGameV1(
        game_id=game_id,
        game_date=_iso(raw.get("game_date")),
        tipoff=raw.get("game_time"),
        state=state,
        home={"team_id": raw.get("home_team_id"), "name": raw.get("home_name"), "abbreviation": raw.get("home_abbr")},
        away={"team_id": raw.get("away_team_id"), "name": raw.get("away_name"), "abbreviation": raw.get("away_abbr")},
        matchup_priority={
            "score": round(priority_score, 1),
            "rank_basis": "editorial_context_only",
            "reasons": priority_reasons,
        },
        signals={
            "environment": _json_ready(environment),
            "schedule_pressure": schedule,
            "team_form": team_form,
            "availability_uncertainty": availability,
            "market_observation": _json_ready(market),
        },
        players_to_watch=_json_ready(players),
        provenance={
            "availability": {
                "home": home_availability,
                "away": away_availability,
                "overall": overall_availability,
            },
            "team_snapshot": _json_ready(raw.get("team_snapshot")),
            "environment_snapshot": _json_ready(environment),
            "market_observation": _json_ready(market),
        },
        market=_json_ready(market),
    )

    insights: List[DailyInsightV1] = []
    env_as_of = _iso(environment.get("feature_as_of"))
    env_completeness = str(environment.get("completeness") or "unknown")
    pace = _number(environment.get("pace_projection"))
    if pace is not None:
        label = environment.get("pace_label") or "pace context"
        insights.append(_insight(
            target_date,
            "pace_context",
            20,
            f"{raw.get('away_abbr')} at {raw.get('home_abbr')}: {pace:.1f} possessions",
            f"The game carries {label} context from the stored game-environment snapshot; this is descriptive, not a prediction.",
            game_id=game_id,
            as_of=env_as_of,
            completeness=env_completeness,
            metric_context={"pace_projection": round(pace, 1), "calculation_version": environment.get("calculation_version")},
        ))

    scoring = _number(environment.get("scoring_env_index"))
    if scoring is not None:
        insights.append(_insight(
            target_date,
            "scoring_environment",
            25,
            f"{raw.get('away_abbr')} at {raw.get('home_abbr')}: scoring environment {scoring:.1f}",
            "The scoring index summarizes stored recent team and game-environment inputs; it is not a projected total.",
            game_id=game_id,
            as_of=env_as_of,
            completeness=env_completeness,
            metric_context={"scoring_env_index": round(scoring, 1), "calculation_version": environment.get("calculation_version")},
        ))

    for side, availability in (("home", home_availability), ("away", away_availability)):
        counts = availability.get("status_counts") or {}
        unresolved = int(availability.get("unresolved_count") or 0)
        flagged = sum(counts.get(status, 0) for status in ("out", "doubtful", "questionable"))
        if flagged or unresolved:
            team = raw.get(f"{side}_abbr") or raw.get(f"{side}_name")
            insights.append(_insight(
                target_date,
                "availability_uncertainty",
                10,
                f"{team}: availability needs attention",
                f"The official availability evidence contains {flagged} non-available/questionable status record(s) and {unresolved} unresolved record(s).",
                game_id=game_id,
                as_of=availability.get("as_of"),
                completeness=str(availability.get("completeness") or "unknown"),
                metric_context={"status_counts": counts, "unresolved_count": unresolved},
            ))

    for side in ("home", "away"):
        schedule_data = schedule[side]
        if schedule_data["flags"]:
            team = raw.get(f"{side}_abbr") or raw.get(f"{side}_name")
            insights.append(_insight(
                target_date,
                "schedule_pressure",
                30,
                f"{team}: {', '.join(schedule_data['flags'])}",
                "Schedule pressure is shown as a context flag from the stored team schedule factors; it does not imply a performance outcome.",
                game_id=game_id,
                team_id=raw.get(f"{side}_team_id"),
                completeness=schedule_data.get("status", "unknown"),
                metric_context=schedule_data,
            ))

    for side in ("home", "away"):
        form = team_form[side]
        delta = form.get("net_rating_delta")
        if delta is not None and abs(delta) >= 3:
            team = raw.get(f"{side}_abbr") or raw.get(f"{side}_name")
            direction = "up" if delta > 0 else "down"
            insights.append(_insight(
                target_date,
                "team_form",
                15,
                f"{team}: recent form is {direction} {abs(delta):.1f}",
                "This is the stored recent-versus-season net-rating delta and should be read as descriptive form context.",
                game_id=game_id,
                team_id=raw.get(f"{side}_team_id"),
                metric_context={"net_rating_delta": delta, "flags": form.get("flags", [])},
            ))

    if market:
        insights.append(_insight(
            target_date,
            "market_coverage",
            35,
            f"{raw.get('away_abbr')} at {raw.get('home_abbr')}: market snapshot observed",
            "This is a timestamped sportsbook observation for context only; it is not a model edge or recommendation.",
            game_id=game_id,
            source=str(market.get("source") or "nba_live_odds"),
            as_of=market.get("markets", [{}])[0].get("observed_at") if market.get("markets") else None,
            completeness=str(market.get("completeness") or "unknown"),
            metric_context={
                "books_count": market.get("books_count", 0),
                "observations_total": market.get("observations_total", 0),
            },
        ))

    return game, insights


def build_daily_intelligence_v1(
    target_date: Optional[date] = None,
    season: Optional[str] = None,
) -> DailyIntelligenceV1:
    """Build the deterministic, read-only Daily Intelligence V1 package."""
    target_date = target_date or date.today()
    context = build_slate_context(
        target_date=target_date,
        season=season,
        include_odds=True,
        include_injuries=True,
        player_limit_per_team=4,
    )
    raw_games = context.get("games") or []
    built_games: List[DailyGameV1] = []
    insights: List[DailyInsightV1] = []
    for raw_game in raw_games:
        game, game_insights = _build_game(target_date, raw_game)
        built_games.append(game)
        insights.extend(game_insights)

    built_games.sort(
        key=lambda game: (-float(game.matchup_priority.get("score") or 0), game.game_id)
    )
    ranked_games: List[DailyGameV1] = []
    for rank, game in enumerate(built_games, start=1):
        ranked_games.append(DailyGameV1(
            game_id=game.game_id,
            game_date=game.game_date,
            tipoff=game.tipoff,
            state=game.state,
            home=game.home,
            away=game.away,
            matchup_priority={**game.matchup_priority, "rank": rank},
            signals=game.signals,
            players_to_watch=game.players_to_watch,
            provenance=game.provenance,
            market=game.market,
        ))

    hot_players = list(context.get("hot_players") or [])
    cold_players = list(context.get("cold_players") or [])
    insights.insert(0, _insight(
        target_date,
        "slate_summary",
        1,
        f"{len(ranked_games)} game(s) in the slate",
        "The package ranks games by deterministic editorial context signals only; no prediction is included.",
        completeness="complete" if ranked_games else "missing",
        metric_context={"game_count": len(ranked_games)},
    ))
    for player in hot_players[:6]:
        insights.append(_insight(
            target_date,
            "player_watch",
            40,
            f"Watch: {player.get('player_name') or 'Player'} heating up",
            "Player watch is drawn from the stored heat-index snapshot and is descriptive context, not a forecast.",
            team_id=player.get("team_id"),
            metric_context={"player": _json_ready(player)},
        ))
    for player in cold_players[:3]:
        insights.append(_insight(
            target_date,
            "player_watch",
            45,
            f"Watch: {player.get('player_name') or 'Player'} cooling off",
            "Player watch is drawn from the stored heat-index snapshot and is descriptive context, not a forecast.",
            team_id=player.get("team_id"),
            metric_context={"player": _json_ready(player)},
        ))

    freshness = _freshness(context.get("freshness") or {}, target_date, context.get("season") or season)
    if not ranked_games:
        status = "empty"
    elif any(game.provenance.get("environment_snapshot") for game in ranked_games):
        status = "available"
    else:
        status = "partial"

    summary = {
        "game_count": len(ranked_games),
        "ranked_game_ids": [game.game_id for game in ranked_games],
        "insight_count": len(insights),
        "players_to_watch_count": len(hot_players[:6]) + len(cold_players[:3]),
        "team_snapshot": _json_ready(context.get("team_snapshot") or {}),
        "player_snapshot": _json_ready(context.get("player_snapshot") or {}),
    }
    return DailyIntelligenceV1(
        contract_version=DAILY_INTELLIGENCE_CONTRACT_VERSION,
        target_date=target_date.isoformat(),
        season=context.get("season") or season,
        status=status,
        freshness=freshness,
        summary=summary,
        games=ranked_games,
        insights=sorted(insights, key=lambda item: (item.priority, item.insight_id)),
        disclaimers=(
            "This V1 package is descriptive and does not contain predictions.",
            "Prior rolling SoS examples remain research-only and are not included in this default payload.",
            "Missing or stale source evidence is preserved as an explicit state; it is never converted to zero.",
        ),
    )
