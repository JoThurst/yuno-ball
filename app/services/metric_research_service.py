"""Pure, versioned research metrics for Program E.

Research metrics are deliberately kept separate from durable product tables
until their source coverage, cutoff behavior, and retrospective performance
have passed the Program E approval gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Optional, Tuple


COMPLETENESS_COMPLETE = "complete"
COMPLETENESS_PARTIAL = "partial"
COMPLETENESS_AFTER_CUTOFF = "after_cutoff"
COMPLETENESS_QUARANTINED = "quarantined"


@dataclass(frozen=True)
class MetricContract:
    """The minimum metadata required before a metric can be evaluated."""

    metric_id: str
    version: str
    grain: str
    required_inputs: Tuple[str, ...]
    required_history: str
    feature_cutoff: str
    interpretation: str
    uncertainty: str
    prohibited_uses: Tuple[str, ...]
    validation_range: str
    update_cadence: str
    consumers: Tuple[str, ...]

    def validate(self) -> None:
        required_text = {
            "metric_id": self.metric_id,
            "version": self.version,
            "grain": self.grain,
            "required_history": self.required_history,
            "feature_cutoff": self.feature_cutoff,
            "interpretation": self.interpretation,
            "uncertainty": self.uncertainty,
            "validation_range": self.validation_range,
            "update_cadence": self.update_cadence,
        }
        missing = [name for name, value in required_text.items() if not value]
        if missing:
            raise ValueError(f"Metric contract fields are required: {', '.join(missing)}")
        if not self.required_inputs:
            raise ValueError("Metric contract must declare required inputs")
        if not self.prohibited_uses:
            raise ValueError("Metric contract must declare prohibited uses")
        if not self.consumers:
            raise ValueError("Metric contract must declare consumers")


@dataclass(frozen=True)
class MetricResult:
    """A non-persistent metric evaluation with explicit missing-state metadata."""

    metric_id: str
    version: str
    value: Optional[float]
    completeness_status: str
    missing_inputs: Tuple[str, ...]
    components: Tuple[Tuple[str, float], ...]
    explanation: Tuple[str, ...]
    feature_as_of: Optional[datetime]
    data_available_at: Optional[datetime]

    def as_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "version": self.version,
            "value": self.value,
            "completeness_status": self.completeness_status,
            "missing_inputs": list(self.missing_inputs),
            "components": dict(self.components),
            "explanation": list(self.explanation),
            "feature_as_of": _iso(self.feature_as_of),
            "data_available_at": _iso(self.data_available_at),
        }


@dataclass(frozen=True)
class SchedulePressurePrototype:
    """User-language rendering kept separate from the research score."""

    status: str
    label: str
    headline: str
    detail: str
    drivers: Tuple[str, ...]
    caveat: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "label": self.label,
            "headline": self.headline,
            "detail": self.detail,
            "drivers": list(self.drivers),
            "caveat": self.caveat,
        }


@dataclass(frozen=True)
class OpponentDifficultyObservation:
    """Pregame opponent-strength and prior-SoS inputs at one game/team grain."""

    game_id: str
    team_id: int
    season: str
    season_type: str
    feature_as_of: Optional[datetime]
    data_available_at: Optional[datetime]
    opponent_net_rtg_season: Optional[float]
    opponent_net_rtg_lastn: Optional[float]
    team_sos_net_season: Optional[float]
    team_sos_net_lastn: Optional[float]


@dataclass(frozen=True)
class RotationShockPlayerObservation:
    """One explicitly reported player status plus prior role proxies."""

    player_id: int
    player_name: str
    status: str
    prior_minutes: Optional[float]
    prior_usage_percentage: Optional[float]
    prior_assist_percentage: Optional[float]
    report_published_at: Optional[datetime]


@dataclass(frozen=True)
class RotationShockObservation:
    """Pregame availability evidence and prior role inputs for one team/game."""

    game_id: str
    team_id: int
    season: str
    season_type: str
    feature_as_of: Optional[datetime]
    data_available_at: Optional[datetime]
    scheduled_tipoff: Optional[datetime]
    availability_evidence_status: str
    players: Tuple[RotationShockPlayerObservation, ...]


@dataclass(frozen=True)
class OpponentDifficultyPrototype:
    """Raw-unit user-language rendering kept separate from production use."""

    status: str
    headline: str
    detail: str
    drivers: Tuple[str, ...]
    caveat: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "headline": self.headline,
            "detail": self.detail,
            "drivers": list(self.drivers),
            "caveat": self.caveat,
        }


@dataclass(frozen=True)
class OpponentDifficultyScaledPrototype:
    """Research-only wording that combines raw units with prior percentiles."""

    style: str
    status: str
    headline: str
    detail: str
    caveat: str

    def as_dict(self) -> dict:
        return {
            "style": self.style,
            "status": self.status,
            "headline": self.headline,
            "detail": self.detail,
            "caveat": self.caveat,
        }


@dataclass(frozen=True)
class PregamePercentileResult:
    """Point-in-time empirical percentile for a pregame reference value."""

    value: Optional[float]
    percentile: Optional[float]
    rank: Optional[float]
    reference_size: int
    completeness_status: str
    missing_inputs: Tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "value": self.value,
            "percentile": self.percentile,
            "rank": self.rank,
            "reference_size": self.reference_size,
            "completeness_status": self.completeness_status,
            "missing_inputs": list(self.missing_inputs),
        }


@dataclass(frozen=True)
class StyleCollisionPaceResult:
    """Read-only pace interaction result for a paired pregame snapshot."""

    status: str
    home_value: Optional[float]
    away_value: Optional[float]
    combined_value: Optional[float]
    contrast: Optional[float]
    combined_percentile: Optional[float]
    reference_size: int
    missing_inputs: Tuple[str, ...]
    expected_direction: str
    explanation: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "home_value": self.home_value,
            "away_value": self.away_value,
            "combined_value": self.combined_value,
            "contrast": self.contrast,
            "combined_percentile": self.combined_percentile,
            "reference_size": self.reference_size,
            "missing_inputs": list(self.missing_inputs),
            "expected_direction": self.expected_direction,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class StyleCollisionPacePrototype:
    """Research-only user-language rendering for pace interaction."""

    style: str
    status: str
    headline: str
    detail: str
    caveat: str

    def as_dict(self) -> dict:
        return {
            "style": self.style,
            "status": self.status,
            "headline": self.headline,
            "detail": self.detail,
            "caveat": self.caveat,
        }


@dataclass(frozen=True)
class StyleCollisionEdgeSpec:
    """Data-audit specification for one Style Collision Map edge."""

    edge_id: str
    description: str
    required_inputs: Tuple[str, ...]
    expected_direction: str
    status: str
    limitation: str

    def as_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "description": self.description,
            "required_inputs": list(self.required_inputs),
            "expected_direction": self.expected_direction,
            "status": self.status,
            "limitation": self.limitation,
        }


STYLE_COLLISION_EDGE_CATALOG = (
    StyleCollisionEdgeSpec(
        edge_id="pace_preference_interaction",
        description="Both teams' recent pace preferences",
        required_inputs=("pace_lastn",),
        expected_direction="higher combined pace indicates a faster descriptive environment",
        status="supported",
        limitation="Descriptive tempo interaction only; not an outcome estimate.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="rim_frequency_vs_allowance",
        description="Rim frequency versus opponent rim allowance",
        required_inputs=("rim_frequency_lastn", "rim_allowance_lastn"),
        expected_direction="not defined until both offensive and defensive rim inputs exist",
        status="blocked",
        limitation="Neither rim frequency nor rim allowance is stored in the current snapshot grain.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="three_point_rate_vs_allowance",
        description="Three-point preference versus opponent three-point allowance",
        required_inputs=("pct_pts_3pt_lastn", "three_point_allowance_lastn"),
        expected_direction="not defined until opponent allowance is available",
        status="blocked",
        limitation="Three-point scoring share exists, but opponent three-point allowance does not.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="offensive_rebound_vs_defensive_rebound",
        description="Offensive rebounding versus opponent defensive rebounding",
        required_inputs=("orb_pct_lastn", "defensive_rebound_pct_allowed_lastn"),
        expected_direction="not defined until the defensive-rebound counterpart exists",
        status="blocked",
        limitation="Offensive rebound rate exists, but defensive-rebound percentage is not stored.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="turnover_creation_vs_ball_security",
        description="Opponent turnover creation versus team ball security",
        required_inputs=("opponent_tov_creation_lastn", "tov_pct_lastn"),
        expected_direction="not defined without forced-turnover and ball-security separation",
        status="blocked",
        limitation="The current turnover rate does not distinguish forced from unforced turnovers.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="free_throw_pressure_vs_foul_rate",
        description="Free-throw pressure versus opponent foul rate",
        required_inputs=("ftr_lastn", "foul_rate_lastn"),
        expected_direction="not defined until opponent foul rate exists",
        status="blocked",
        limitation="Free-throw rate exists, but opponent foul rate is not stored.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="transition_frequency_vs_transition_defense",
        description="Transition frequency versus opponent transition defense",
        required_inputs=("transition_frequency_lastn", "transition_defense_lastn"),
        expected_direction="not defined until transition inputs exist",
        status="blocked",
        limitation="Neither transition frequency nor transition defense exists in the current snapshot grain.",
    ),
    StyleCollisionEdgeSpec(
        edge_id="assisted_scoring_vs_creation_denial",
        description="Assisted scoring versus opponent creation denial",
        required_inputs=("assisted_scoring_lastn", "creation_denial_lastn"),
        expected_direction="not defined until creation inputs exist",
        status="blocked",
        limitation="Neither assisted scoring nor opponent creation denial is stored.",
    ),
)


STYLE_COLLISION_MAP_CONTRACT = MetricContract(
    metric_id="style_collision_map_context",
    version="style-collision-map-v0.1",
    grain="(game_id, feature_as_of, version, edge_id)",
    required_inputs=("paired_pregame_snapshots", "feature_as_of", "data_available_at"),
    required_history="Prior same-season team snapshots for point-in-time percentile references",
    feature_cutoff="Pregame only; both team perspectives must share the target cutoff and calculation version",
    interpretation="Descriptive matchup-style interaction context; higher interaction strength is not a performance forecast",
    uncertainty="Only explicitly supported edges may be prototyped; blocked edges require source expansion",
    prohibited_uses=(
        "Do not treat an interaction strength as a win-probability or performance estimate",
        "Do not use target-game outcomes, postgame box scores, or current endpoint aggregates",
        "Do not fill unsupported edge inputs with zero or substitute unrelated metrics",
        "Do not publish a style interaction to production until the Program E approval gate passes",
    ),
    validation_range="Edge-specific; percentile and strength scales require an edge contract",
    update_cadence="Research batch; future production cadence requires a separate approved bridge",
    consumers=("Program E retrospective audits and prototypes",),
)
STYLE_COLLISION_MAP_CONTRACT.validate()


@dataclass(frozen=True)
class SchedulePressureObservation:
    """Pregame schedule inputs at one team/game grain.

    The observation mirrors both the versioned team snapshot fields and the
    legacy ``team_schedule_factors`` names. It contains no game outcome or
    postgame field, so it can be reused for leakage-safe retrospective tests.
    """

    game_id: str
    team_id: int
    season: str
    season_type: str
    feature_as_of: Optional[datetime]
    data_available_at: Optional[datetime]
    days_rest: Optional[int]
    opponent_days_rest: Optional[int]
    rest_diff: Optional[int]
    is_b2b: Optional[bool]
    is_3_in_4: Optional[bool]
    is_4_in_5: Optional[bool]
    is_5_in_7: Optional[bool]
    games_last_4: Optional[int]
    games_last_7: Optional[int]


SCHEDULE_PRESSURE_CONTRACT = MetricContract(
    metric_id="schedule_pressure_index",
    version="schedule-pressure-v0.1",
    grain="(game_id, team_id, feature_as_of, version)",
    required_inputs=(
        "days_rest",
        "opponent_days_rest",
        "rest_diff",
        "games_last_4",
        "games_last_7",
        "feature_as_of",
        "data_available_at",
    ),
    required_history="Prior scheduled games for the same team and opponent before the target game",
    feature_cutoff="Pregame only; every input must be available at or before feature_as_of",
    interpretation="A descriptive 0-100 schedule-stress hypothesis; higher means more pregame pressure",
    uncertainty="Research hypothesis; weights are not causal estimates and require retrospective validation",
    prohibited_uses=(
        "Do not interpret the score as a causal estimate of win probability or player performance",
        "Do not use missing inputs as zero pressure",
        "Do not use target-game outcomes, postgame box scores, or market outcomes",
        "Do not publish to production until the Program E approval gate passes",
    ),
    validation_range="0-100 inclusive; exact replay, monotonicity, cutoff, and cross-season stability",
    update_cadence="Research batch; future production cadence requires a separate approved bridge",
    consumers=("Program E retrospective notebooks/reports",),
)
SCHEDULE_PRESSURE_CONTRACT.validate()


OPPONENT_DIFFICULTY_CONTRACT = MetricContract(
    metric_id="opponent_difficulty_context",
    version="opponent-difficulty-v0.1",
    grain="(game_id, team_id, feature_as_of, version)",
    required_inputs=(
        "opponent_net_rtg_season",
        "opponent_net_rtg_lastn",
        "team_sos_net_season",
        "team_sos_net_lastn",
        "feature_as_of",
        "data_available_at",
    ),
    required_history="Exact paired pregame team snapshots built only from prior game facts",
    feature_cutoff="Pregame only; both team perspectives must share the target cutoff and calculation version",
    interpretation="Descriptive opponent difficulty and prior schedule-strength context in net-rating units",
    uncertainty="Raw net-rating context is not a calibrated probability or a causal estimate",
    prohibited_uses=(
        "Do not interpret opponent strength as a standalone win-probability estimate",
        "Do not use target-game outcomes, postgame box scores, or current endpoint season aggregates",
        "Do not convert to a 0-100 score until a pregame-safe reference distribution is validated",
        "Do not publish to production until the Program E approval gate passes",
    ),
    validation_range="Finite net-rating values in points per 100 estimated possessions; no fixed 0-100 scale yet",
    update_cadence="Research batch; future production cadence requires a separate approved bridge",
    consumers=("Program E retrospective notebooks/reports", "Program E user-language prototype"),
)
OPPONENT_DIFFICULTY_CONTRACT.validate()


ROTATION_SHOCK_CONTRACT = MetricContract(
    metric_id="rotation_shock_exposure",
    version="rotation-shock-v0.1",
    grain="(game_id, team_id, feature_as_of, version)",
    required_inputs=(
        "pregame availability evidence",
        "prior actual minutes",
        "prior usage percentage",
        "prior assist percentage",
        "feature_as_of",
        "data_available_at",
        "scheduled_tipoff",
    ),
    required_history="Prior player-game facts for the same player before the target game",
    feature_cutoff="Pregame only; availability and role inputs must be available before scheduled tipoff",
    interpretation="Descriptive prior role exposure attached to explicitly reported unavailable or uncertain players",
    uncertainty="A minutes exposure proxy; it is not expected minutes, replacement quality, or a performance estimate",
    prohibited_uses=(
        "Do not infer availability or health from an absent report row",
        "Do not call prior minutes expected minutes or treat status weights as probabilities",
        "Do not use target-game outcomes, target-game minutes, or postgame facts",
        "Do not publish to production until historical availability coverage and source timing pass review",
    ),
    validation_range="0-100 inclusive exposure score; raw role components must remain visible",
    update_cadence="Research batch; future production cadence requires a separate approved bridge",
    consumers=("Program E retrospective audits and prototypes",),
)
ROTATION_SHOCK_CONTRACT.validate()


def calculate_schedule_pressure(observation: SchedulePressureObservation) -> MetricResult:
    """Calculate the research-only Schedule Pressure Index.

    The candidate weighting is intentionally explicit and versioned:
    45% short-rest pressure, 35% schedule-density pressure, and 20% rest
    disadvantage versus the opponent. The calculator returns no score for
    missing, invalid, or post-cutoff inputs.
    """

    missing = _missing_required_inputs(observation)
    if missing:
        return _result(
            observation,
            completeness_status=COMPLETENESS_PARTIAL,
            missing_inputs=missing,
            explanation=("Metric withheld because required pregame inputs are missing.",),
        )

    assert observation.feature_as_of is not None
    assert observation.data_available_at is not None
    feature_as_of = _aware_utc(observation.feature_as_of)
    data_available_at = _aware_utc(observation.data_available_at)
    if data_available_at > feature_as_of:
        return _result(
            observation,
            completeness_status=COMPLETENESS_AFTER_CUTOFF,
            missing_inputs=("data_available_at_after_feature_as_of",),
            explanation=("Metric withheld because an input arrives after the declared cutoff.",),
        )

    invalid = _invalid_inputs(observation)
    if invalid:
        return _result(
            observation,
            completeness_status=COMPLETENESS_QUARANTINED,
            missing_inputs=invalid,
            explanation=("Metric withheld because source inputs fail consistency checks.",),
        )

    days_rest = observation.days_rest
    games_last_4 = observation.games_last_4
    games_last_7 = observation.games_last_7
    rest_diff = observation.rest_diff
    assert days_rest is not None
    assert games_last_4 is not None
    assert games_last_7 is not None
    assert rest_diff is not None

    short_rest = _clamp((2 - days_rest) / 2, 0.0, 1.0)
    density = max(
        _clamp(games_last_4 / 2, 0.0, 1.0),
        _clamp(games_last_7 / 4, 0.0, 1.0),
    )
    rest_disadvantage = _clamp(-rest_diff / 2, 0.0, 1.0)
    value = round(100 * (0.45 * short_rest + 0.35 * density + 0.20 * rest_disadvantage), 4)
    components = (
        ("short_rest_pressure", round(short_rest, 4)),
        ("schedule_density_pressure", round(density, 4)),
        ("opponent_rest_disadvantage", round(rest_disadvantage, 4)),
    )
    explanation = _explain(observation)
    return _result(
        observation,
        completeness_status=COMPLETENESS_COMPLETE,
        missing_inputs=(),
        value=value,
        components=components,
        explanation=explanation,
    )


def calculate_rotation_shock(observation: RotationShockObservation) -> MetricResult:
    """Calculate the research-only prior role-exposure proxy.

    Status weights are deliberately a hypothesis: Out=1.0, Doubtful=0.75,
    and Questionable=0.5. The score uses prior actual minutes against a
    nominal 240 team-minute baseline. Usage and assist percentage are retained
    as minutes-weighted context, not as expected replacement performance.
    """

    missing = []
    if observation.feature_as_of is None:
        missing.append("feature_as_of")
    if observation.data_available_at is None:
        missing.append("data_available_at")
    if observation.scheduled_tipoff is None:
        missing.append("scheduled_tipoff")
    if observation.availability_evidence_status != "complete":
        missing.append("availability_evidence_status")
    for player in observation.players:
        prefix = f"player_{player.player_id}"
        if player.report_published_at is None:
            missing.append(f"{prefix}.report_published_at")
        if player.status not in {"Available", "Probable", "Questionable", "Doubtful", "Out"}:
            missing.append(f"{prefix}.status")
        if player.status in {"Questionable", "Doubtful", "Out"}:
            for field_name, value in (
                ("prior_minutes", player.prior_minutes),
                ("prior_usage_percentage", player.prior_usage_percentage),
                ("prior_assist_percentage", player.prior_assist_percentage),
            ):
                if value is None:
                    missing.append(f"{prefix}.{field_name}")
    if missing:
        return _rotation_result(
            observation,
            completeness_status=COMPLETENESS_PARTIAL,
            missing_inputs=tuple(missing),
            explanation=(
                "Rotation Shock is withheld because the pregame availability "
                "evidence or prior role baseline is incomplete.",
            ),
        )

    assert observation.feature_as_of is not None
    assert observation.data_available_at is not None
    assert observation.scheduled_tipoff is not None
    feature_as_of = _aware_utc(observation.feature_as_of)
    if _aware_utc(observation.data_available_at) > feature_as_of:
        return _rotation_result(
            observation,
            completeness_status=COMPLETENESS_AFTER_CUTOFF,
            missing_inputs=("data_available_at_after_feature_as_of",),
            explanation=("Rotation Shock is withheld because an input arrived after the declared cutoff.",),
        )
    if feature_as_of >= _aware_utc(observation.scheduled_tipoff):
        return _rotation_result(
            observation,
            completeness_status=COMPLETENESS_AFTER_CUTOFF,
            missing_inputs=("feature_as_of_not_pregame",),
            explanation=("Rotation Shock is withheld because the feature cutoff is not before tipoff.",),
        )

    invalid = []
    for player in observation.players:
        if _aware_utc(player.report_published_at) > feature_as_of:  # type: ignore[arg-type]
            return _rotation_result(
                observation,
                completeness_status=COMPLETENESS_AFTER_CUTOFF,
                missing_inputs=(f"player_{player.player_id}.report_after_feature_as_of",),
                explanation=("Rotation Shock is withheld because a status was published after the cutoff.",),
            )
        for field_name in ("prior_minutes", "prior_usage_percentage", "prior_assist_percentage"):
            value = getattr(player, field_name)
            if value is not None and (not isfinite(value) or value < 0):
                invalid.append(f"player_{player.player_id}.{field_name}_invalid")
        for field_name in ("prior_usage_percentage", "prior_assist_percentage"):
            value = getattr(player, field_name)
            if value is not None and value > 100:
                invalid.append(f"player_{player.player_id}.{field_name}_out_of_range")
    if invalid:
        return _rotation_result(
            observation,
            completeness_status=COMPLETENESS_QUARANTINED,
            missing_inputs=tuple(invalid),
            explanation=("Rotation Shock is withheld because a prior role input fails validation.",),
        )

    weights = {"Out": 1.0, "Doubtful": 0.75, "Questionable": 0.5}
    at_risk = [player for player in observation.players if player.status in weights]
    weighted_minutes = sum(weights[player.status] * player.prior_minutes for player in at_risk)  # type: ignore[operator]
    out_minutes = sum(player.prior_minutes for player in at_risk if player.status == "Out")  # type: ignore[union-attr]
    doubtful_minutes = sum(player.prior_minutes for player in at_risk if player.status == "Doubtful")  # type: ignore[union-attr]
    questionable_minutes = sum(player.prior_minutes for player in at_risk if player.status == "Questionable")  # type: ignore[union-attr]
    usage_exposure = sum(
        player.prior_minutes * player.prior_usage_percentage / 100  # type: ignore[operator]
        for player in at_risk
    )
    creation_exposure = sum(
        player.prior_minutes * player.prior_assist_percentage / 100  # type: ignore[operator]
        for player in at_risk
    )
    score = round(_clamp(weighted_minutes / 240 * 100, 0.0, 100.0), 4)
    if at_risk:
        explanation = (
            f"{sum(player.status == 'Out' for player in at_risk)} player(s) were listed Out and "
            f"{sum(player.status in {'Doubtful', 'Questionable'} for player in at_risk)} were listed "
            f"Doubtful or Questionable. Their weighted prior minutes at risk were "
            f"{weighted_minutes:.1f} of a nominal 240 team minutes ({score:.1f}/100).",
            "Minutes-weighted usage and assist percentages are role-exposure proxies; "
            "they do not estimate replacement performance.",
        )
    else:
        explanation = (
            "No explicitly reported unavailable or uncertain players were supplied; "
            "this is not proof that every player was available.",
        )
    components = (
        ("out_minutes_at_risk", round(out_minutes, 4)),
        ("doubtful_minutes_at_risk", round(doubtful_minutes, 4)),
        ("questionable_minutes_at_risk", round(questionable_minutes, 4)),
        ("weighted_minutes_at_risk", round(weighted_minutes, 4)),
        ("minutes_exposure_score", score),
        ("minutes_weighted_usage_exposure", round(usage_exposure, 4)),
        ("minutes_weighted_creation_exposure", round(creation_exposure, 4)),
        ("listed_role_player_count", float(len(at_risk))),
    )
    return _rotation_result(
        observation,
        completeness_status=COMPLETENESS_COMPLETE,
        missing_inputs=(),
        value=score,
        components=components,
        explanation=explanation,
    )


def build_opponent_difficulty_prototype(
    observation: OpponentDifficultyObservation,
    *,
    team_name: str = "This team",
    opponent_name: str = "the opponent",
) -> OpponentDifficultyPrototype:
    """Render raw opponent-strength context without selecting a composite score."""

    caveat = (
        "Describes pregame opponent and prior-schedule strength in net-rating "
        "units; it is not a performance or outcome prediction."
    )
    missing = list(_missing_opponent_difficulty_inputs(observation))
    if missing:
        return OpponentDifficultyPrototype(
            status=COMPLETENESS_PARTIAL,
            headline=f"{team_name}: opponent difficulty unavailable",
            detail="Opponent difficulty context is unavailable because required pregame strength inputs are incomplete.",
            drivers=(),
            caveat=caveat,
        )

    assert observation.feature_as_of is not None
    assert observation.data_available_at is not None
    if _aware_utc(observation.data_available_at) > _aware_utc(observation.feature_as_of):
        return OpponentDifficultyPrototype(
            status=COMPLETENESS_AFTER_CUTOFF,
            headline=f"{team_name}: opponent difficulty withheld",
            detail="Opponent difficulty context is withheld because an input was not available before tipoff.",
            drivers=(),
            caveat=caveat,
        )

    opponent_season = _signed(observation.opponent_net_rtg_season)
    opponent_recent = _signed(observation.opponent_net_rtg_lastn)
    sos_season = _signed(observation.team_sos_net_season)
    sos_recent = _signed(observation.team_sos_net_lastn)
    drivers = (
        f"{opponent_name} pregame net rating: {opponent_season} season, {opponent_recent} recent",
        f"prior opponent average: {sos_season} season, {sos_recent} recent",
    )
    detail = (
        f"Opponent context for {team_name}: {opponent_name} posted a net "
        f"rating of {opponent_season} this season and {opponent_recent} over "
        f"its recent games. The previous opponents for {team_name} averaged "
        f"{sos_season} this season and {sos_recent} recently. Higher values "
        "indicate stronger opponents."
    )
    return OpponentDifficultyPrototype(
        status=COMPLETENESS_COMPLETE,
        headline=f"{team_name}: opponent difficulty context",
        detail=detail,
        drivers=drivers,
        caveat=caveat,
    )


def build_opponent_difficulty_scaled_prototype(
    observation: OpponentDifficultyObservation,
    *,
    opponent_season_percentile: Optional[float],
    opponent_recent_percentile: Optional[float],
    team_sos_season_percentile: Optional[float],
    team_sos_recent_percentile: Optional[float],
    style: str = "raw_plus_percentile",
    team_name: str = "This team",
    opponent_name: str = "the opponent",
) -> OpponentDifficultyScaledPrototype:
    """Render selectable research wording without creating a consumer."""

    caveat = (
        "Describes pregame opponent and prior-schedule strength. Percentiles "
        "are relative to earlier same-season observations; this is not a "
        "performance or outcome prediction."
    )
    if style not in {"raw_plus_percentile", "percentile_first", "compact"}:
        raise ValueError(f"Unknown opponent-difficulty wording style: {style}")

    missing = list(_missing_opponent_difficulty_inputs(observation))
    percentile_values = {
        "opponent_season_percentile": opponent_season_percentile,
        "opponent_recent_percentile": opponent_recent_percentile,
        "team_sos_season_percentile": team_sos_season_percentile,
        "team_sos_recent_percentile": team_sos_recent_percentile,
    }
    missing.extend(name for name, value in percentile_values.items() if value is None)
    invalid_percentiles = tuple(
        f"{name}_out_of_range"
        for name, value in percentile_values.items()
        if value is not None and (not isfinite(value) or not 0 <= value <= 100)
    )
    if missing or invalid_percentiles:
        return OpponentDifficultyScaledPrototype(
            style=style,
            status=COMPLETENESS_QUARANTINED if invalid_percentiles else COMPLETENESS_PARTIAL,
            headline=f"{team_name}: opponent difficulty unavailable",
            detail="Scaled opponent context is unavailable because the pregame raw values or reference percentiles are incomplete.",
            caveat=caveat,
        )

    assert observation.feature_as_of is not None
    assert observation.data_available_at is not None
    if _aware_utc(observation.data_available_at) > _aware_utc(observation.feature_as_of):
        return OpponentDifficultyScaledPrototype(
            style=style,
            status=COMPLETENESS_AFTER_CUTOFF,
            headline=f"{team_name}: opponent difficulty withheld",
            detail="Scaled opponent context is withheld because an input was not available before tipoff.",
            caveat=caveat,
        )

    opponent_season = _signed(observation.opponent_net_rtg_season)
    opponent_recent = _signed(observation.opponent_net_rtg_lastn)
    sos_season = _signed(observation.team_sos_net_season)
    sos_recent = _signed(observation.team_sos_net_lastn)
    opponent_season_rank = _ordinal(opponent_season_percentile)
    opponent_recent_rank = _ordinal(opponent_recent_percentile)
    sos_season_rank = _ordinal(team_sos_season_percentile)
    sos_recent_rank = _ordinal(team_sos_recent_percentile)

    if style == "raw_plus_percentile":
        detail = (
            f"Opponent context for {team_name}: {opponent_name} posted a net rating "
            f"of {opponent_season} this season and {opponent_recent} recently, "
            f"around the {opponent_season_rank} percentile this season and "
            f"{opponent_recent_rank} percentile recently among earlier "
            "opponent-strength observations. Previous "
            f"opponents for {team_name} averaged {sos_season} this season and "
            f"{sos_recent} recently, around the {sos_season_rank} percentile this "
            f"season and {sos_recent_rank} percentile recently. Higher values indicate stronger "
            "opponents."
        )
    elif style == "percentile_first":
        detail = (
            f"Opponent context for {team_name} — {opponent_name}: around the "
            f"{opponent_season_rank} percentile for season opponent strength "
            f"and the {opponent_recent_rank} percentile recently "
            f"({opponent_season} season, {opponent_recent} recent). Prior "
            f"opponents for {team_name}: around the "
            f"{sos_season_rank} percentile this season and the {sos_recent_rank} "
            f"recently ({sos_season} season, {sos_recent} recent). Higher values "
            "indicate stronger opponents."
        )
    else:
        detail = (
            f"Matchup context for {team_name} vs. {opponent_name}: about the "
            f"{opponent_season_rank} percentile this season ({opponent_season}) "
            f"and {opponent_recent_rank} recently ({opponent_recent}). Prior "
            f"schedule strength: {sos_season_rank} season ({sos_season}) and "
            f"{sos_recent_rank} recently ({sos_recent}). Higher values mean "
            "stronger opponents."
        )
    return OpponentDifficultyScaledPrototype(
        style=style,
        status=COMPLETENESS_COMPLETE,
        headline=f"{team_name}: scaled opponent context",
        detail=detail,
        caveat=caveat,
    )


def calculate_pregame_percentile(
    value: Optional[float],
    prior_values: Iterable[Optional[float]],
    *,
    minimum_reference_size: int = 20,
) -> PregamePercentileResult:
    """Calculate a leakage-safe empirical percentile from prior observations.

    The reference distribution must be assembled by the caller in strict
    feature-cutoff order. Values from the target game or any later cutoff are
    therefore never accepted here. Midranks make ties deterministic while
    preserving a bounded 0-100 presentation for research comparisons.
    """

    if minimum_reference_size < 2:
        raise ValueError("minimum_reference_size must be at least 2")
    if value is None:
        return PregamePercentileResult(
            value=None,
            percentile=None,
            rank=None,
            reference_size=0,
            completeness_status=COMPLETENESS_PARTIAL,
            missing_inputs=("value_missing",),
        )
    if not isfinite(value):
        return PregamePercentileResult(
            value=None,
            percentile=None,
            rank=None,
            reference_size=0,
            completeness_status=COMPLETENESS_QUARANTINED,
            missing_inputs=("value_not_finite",),
        )

    usable = sorted(
        candidate
        for candidate in prior_values
        if candidate is not None and isfinite(candidate)
    )
    reference_size = len(usable)
    if reference_size < minimum_reference_size:
        return PregamePercentileResult(
            value=round(value, 4),
            percentile=None,
            rank=None,
            reference_size=reference_size,
            completeness_status=COMPLETENESS_PARTIAL,
            missing_inputs=("insufficient_reference_history",),
        )

    less = sum(candidate < value for candidate in usable)
    equal = sum(candidate == value for candidate in usable)
    rank = less + (equal + 1) / 2
    percentile = 100 * (less + 0.5 * equal) / reference_size
    return PregamePercentileResult(
        value=round(value, 4),
        percentile=round(percentile, 4),
        rank=round(rank, 4),
        reference_size=reference_size,
        completeness_status=COMPLETENESS_COMPLETE,
        missing_inputs=(),
    )


def calculate_style_collision_pace(
    home_pace: Optional[float],
    away_pace: Optional[float],
    prior_combined_paces: Iterable[Optional[float]],
    *,
    minimum_reference_size: int = 20,
) -> StyleCollisionPaceResult:
    """Calculate descriptive pace interaction from paired pregame inputs."""

    expected_direction = (
        "higher combined pace indicates a faster environment; higher contrast "
        "indicates more different team preferences"
    )
    missing = []
    if home_pace is None:
        missing.append("home_pace_lastn")
    if away_pace is None:
        missing.append("away_pace_lastn")
    if missing:
        return StyleCollisionPaceResult(
            status=COMPLETENESS_PARTIAL,
            home_value=home_pace,
            away_value=away_pace,
            combined_value=None,
            contrast=None,
            combined_percentile=None,
            reference_size=0,
            missing_inputs=tuple(missing),
            expected_direction=expected_direction,
            explanation="Pace interaction withheld because a paired pregame pace input is missing.",
        )
    if (
        not isfinite(home_pace)
        or not isfinite(away_pace)
        or home_pace < 0
        or away_pace < 0
    ):
        return StyleCollisionPaceResult(
            status=COMPLETENESS_QUARANTINED,
            home_value=None,
            away_value=None,
            combined_value=None,
            contrast=None,
            combined_percentile=None,
            reference_size=0,
            missing_inputs=("pace_value_invalid",),
            expected_direction=expected_direction,
            explanation="Pace interaction withheld because a paired pregame pace input is invalid.",
        )

    combined = round((home_pace + away_pace) / 2, 4)
    contrast = round(abs(home_pace - away_pace), 4)
    percentile = calculate_pregame_percentile(
        combined,
        prior_combined_paces,
        minimum_reference_size=minimum_reference_size,
    )
    if percentile.completeness_status != COMPLETENESS_COMPLETE:
        return StyleCollisionPaceResult(
            status=percentile.completeness_status,
            home_value=round(home_pace, 4),
            away_value=round(away_pace, 4),
            combined_value=combined,
            contrast=contrast,
            combined_percentile=None,
            reference_size=percentile.reference_size,
            missing_inputs=percentile.missing_inputs,
            expected_direction=expected_direction,
            explanation="Pace interaction is available, but its historical percentile reference is not yet large enough.",
        )
    return StyleCollisionPaceResult(
        status=COMPLETENESS_COMPLETE,
        home_value=round(home_pace, 4),
        away_value=round(away_pace, 4),
        combined_value=combined,
        contrast=contrast,
        combined_percentile=percentile.percentile,
        reference_size=percentile.reference_size,
        missing_inputs=(),
        expected_direction=expected_direction,
        explanation=(
            f"Recent pace preferences average {combined:.1f} possessions per game "
            f"(around the {_ordinal(percentile.percentile)} percentile of earlier observations), "
            f"with a {contrast:.1f} possession gap between teams."
        ),
    )


def _ordinal(value: Optional[float]) -> str:
    assert value is not None
    # Percentiles are non-negative; use human-facing half-up rounding rather
    # than Python's banker rounding (for example, 52.5 -> 53rd).
    number = int(value + 0.5)
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def build_style_collision_pace_prototype(
    result: StyleCollisionPaceResult,
    *,
    style: str = "percentile_first",
    home_name: str = "Home team",
    away_name: str = "the opponent",
) -> StyleCollisionPacePrototype:
    """Render selectable, non-predictive wording for a pace result."""

    if style not in {"raw_plus_percentile", "percentile_first", "compact"}:
        raise ValueError(f"Unknown pace wording style: {style}")

    caveat = (
        "Summarizes the teams' recent pace profiles using earlier same-season "
        "paired references; it is not a prediction of the game's final pace, "
        "total, or outcome."
    )
    if result.status != COMPLETENESS_COMPLETE:
        if result.combined_value is not None and result.contrast is not None:
            detail = (
                f"Recent pace preferences for {home_name} and {away_name} average "
                f"{result.combined_value:.1f} possessions per game, with a "
                f"{result.contrast:.1f} possession gap. The percentile comparison "
                "is withheld because earlier same-season reference history is "
                "incomplete."
            )
        else:
            detail = result.explanation
        return StyleCollisionPacePrototype(
            style=style,
            status=result.status,
            headline=f"{home_name}: pace interaction unavailable",
            detail=detail,
            caveat=caveat,
        )

    assert result.home_value is not None
    assert result.away_value is not None
    assert result.combined_value is not None
    assert result.contrast is not None
    assert result.combined_percentile is not None
    percentile_rank = _ordinal(result.combined_percentile)

    if style == "raw_plus_percentile":
        detail = (
            f"Recent pace profiles: {home_name} at {result.home_value:.1f} and "
            f"{away_name} at {result.away_value:.1f} possessions per game. "
            f"Together, those profiles average {result.combined_value:.1f} "
            f"possessions, around the {percentile_rank} percentile of earlier "
            f"same-season paired games. The profiles are {result.contrast:.1f} "
            "possessions apart."
        )
    elif style == "percentile_first":
        detail = (
            f"Recent pace context for {home_name} vs. {away_name}: "
            f"{result.combined_value:.1f} possessions per game, around the "
            f"{percentile_rank} percentile of earlier same-season paired games. "
            f"{home_name} has recently played at {result.home_value:.1f} and "
            f"{away_name} at {result.away_value:.1f}; their profiles are "
            f"{result.contrast:.1f} possessions apart."
        )
    else:
        detail = (
            f"Recent pace: {result.combined_value:.1f} possessions per game "
            f"({percentile_rank} percentile); {home_name} "
            f"{result.home_value:.1f}, {away_name} {result.away_value:.1f}; "
            f"{result.contrast:.1f}-possession difference."
        )
    return StyleCollisionPacePrototype(
        style=style,
        status=result.status,
        headline=f"{home_name}: pace interaction context",
        detail=detail,
        caveat=caveat,
    )


def build_schedule_pressure_prototype(
    observation: SchedulePressureObservation,
    result: MetricResult,
    *,
    team_name: str = "This team",
    opponent_name: str = "the opponent",
) -> SchedulePressurePrototype:
    """Render a cautious, user-facing prototype without creating a consumer.

    This function intentionally accepts the already-evaluated ``MetricResult``
    so the wording cannot bypass its cutoff or missingness state.
    """

    caveat = (
        "Describes pregame schedule context from rest and recent game density; "
        "it is not a prediction of performance or outcome. Opponent strength and "
        "travel are not included in this version."
    )
    if result.completeness_status != COMPLETENESS_COMPLETE or result.value is None:
        messages = {
            COMPLETENESS_PARTIAL: "Schedule strain is unavailable because the pregame schedule history is incomplete.",
            COMPLETENESS_AFTER_CUTOFF: "Schedule strain is withheld because an input was not available before tipoff.",
            COMPLETENESS_QUARANTINED: "Schedule strain is withheld because the schedule inputs do not agree.",
        }
        detail = messages.get(
            result.completeness_status,
            "Schedule strain is unavailable because required pregame inputs are incomplete.",
        )
        return SchedulePressurePrototype(
            status=result.completeness_status,
            label="Unavailable",
            headline=f"{team_name}: schedule strain unavailable",
            detail=detail,
            drivers=(),
            caveat=caveat,
        )

    value = result.value
    if value < 25:
        label = "Low schedule strain"
    elif value < 50:
        label = "Moderate schedule strain"
    elif value < 75:
        label = "Elevated schedule strain"
    else:
        label = "High schedule strain"

    drivers = []
    if observation.is_b2b:
        drivers.append("playing back-to-back games")
    if observation.is_3_in_4:
        drivers.append("playing 3 games in 4 days")
    elif observation.is_4_in_5:
        drivers.append("playing 4 games in 5 days")
    if observation.is_5_in_7:
        drivers.append("playing 5 games in 7 days")
    if observation.rest_diff is not None:
        if observation.rest_diff < 0:
            days = abs(observation.rest_diff)
            drivers.append(f"{days} fewer rest day{'s' if days != 1 else ''} than {opponent_name}")
        elif observation.rest_diff > 0:
            days = observation.rest_diff
            drivers.append(f"{days} more rest day{'s' if days != 1 else ''} than {opponent_name}")
    if not drivers:
        drivers.append("no major congestion or rest-disadvantage flag detected")

    detail = (
        f"Schedule context for {team_name}: {label.lower()} ({value:.0f}/100). "
        "Key drivers: " + ", ".join(drivers) + "."
    )
    return SchedulePressurePrototype(
        status=result.completeness_status,
        label=label,
        headline=f"{team_name}: {label}",
        detail=detail,
        drivers=tuple(drivers),
        caveat=caveat,
    )


def _missing_required_inputs(observation: SchedulePressureObservation) -> Tuple[str, ...]:
    values = {
        "days_rest": observation.days_rest,
        "opponent_days_rest": observation.opponent_days_rest,
        "rest_diff": observation.rest_diff,
        "games_last_4": observation.games_last_4,
        "games_last_7": observation.games_last_7,
        "feature_as_of": observation.feature_as_of,
        "data_available_at": observation.data_available_at,
    }
    return tuple(name for name, value in values.items() if value is None)


def _missing_opponent_difficulty_inputs(
    observation: OpponentDifficultyObservation,
) -> Tuple[str, ...]:
    values = {
        "opponent_net_rtg_season": observation.opponent_net_rtg_season,
        "opponent_net_rtg_lastn": observation.opponent_net_rtg_lastn,
        "team_sos_net_season": observation.team_sos_net_season,
        "team_sos_net_lastn": observation.team_sos_net_lastn,
        "feature_as_of": observation.feature_as_of,
        "data_available_at": observation.data_available_at,
    }
    return tuple(name for name, value in values.items() if value is None)


def _invalid_inputs(observation: SchedulePressureObservation) -> Tuple[str, ...]:
    invalid = []
    for name in ("days_rest", "opponent_days_rest", "games_last_4", "games_last_7"):
        value = getattr(observation, name)
        if value is not None and value < 0:
            invalid.append(f"{name}_negative")
    if observation.rest_diff != observation.days_rest - observation.opponent_days_rest:
        invalid.append("rest_diff_inconsistent")
    if observation.is_b2b is not None and observation.is_b2b != (observation.days_rest == 0):
        invalid.append("is_b2b_inconsistent")
    if observation.is_3_in_4 is not None and observation.is_3_in_4 != (observation.games_last_4 >= 2):
        invalid.append("is_3_in_4_inconsistent")
    if observation.is_5_in_7 is not None and observation.is_5_in_7 != (observation.games_last_7 >= 4):
        invalid.append("is_5_in_7_inconsistent")
    return tuple(invalid)


def _explain(observation: SchedulePressureObservation) -> Tuple[str, ...]:
    explanations = []
    if observation.is_b2b:
        explanations.append("back-to-back")
    if observation.is_3_in_4:
        explanations.append("3-in-4 schedule")
    if observation.is_4_in_5:
        explanations.append("4-in-5 schedule")
    if observation.is_5_in_7:
        explanations.append("5-in-7 schedule")
    if observation.rest_diff is not None and observation.rest_diff < 0:
        explanations.append(f"{abs(observation.rest_diff)} fewer rest days than opponent")
    if not explanations:
        explanations.append("no elevated schedule flag")
    return tuple(explanations)


def _result(
    observation: SchedulePressureObservation,
    *,
    completeness_status: str,
    missing_inputs: Tuple[str, ...],
    explanation: Tuple[str, ...],
    value: Optional[float] = None,
    components: Tuple[Tuple[str, float], ...] = (),
) -> MetricResult:
    return MetricResult(
        metric_id=SCHEDULE_PRESSURE_CONTRACT.metric_id,
        version=SCHEDULE_PRESSURE_CONTRACT.version,
        value=value,
        completeness_status=completeness_status,
        missing_inputs=missing_inputs,
        components=components,
        explanation=explanation,
        feature_as_of=observation.feature_as_of,
        data_available_at=observation.data_available_at,
    )


def _rotation_result(
    observation: RotationShockObservation,
    *,
    completeness_status: str,
    missing_inputs: Tuple[str, ...],
    explanation: Tuple[str, ...],
    value: Optional[float] = None,
    components: Tuple[Tuple[str, float], ...] = (),
) -> MetricResult:
    return MetricResult(
        metric_id=ROTATION_SHOCK_CONTRACT.metric_id,
        version=ROTATION_SHOCK_CONTRACT.version,
        value=value,
        completeness_status=completeness_status,
        missing_inputs=missing_inputs,
        components=components,
        explanation=explanation,
        feature_as_of=observation.feature_as_of,
        data_available_at=observation.data_available_at,
    )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return _aware_utc(value).isoformat() if value is not None else None


def _signed(value: float) -> str:
    return f"{value:+.1f}"
