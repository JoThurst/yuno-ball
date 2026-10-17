from datetime import datetime, timezone

from app.services.metric_research_service import (
    COMPLETENESS_AFTER_CUTOFF,
    COMPLETENESS_COMPLETE,
    COMPLETENESS_PARTIAL,
    COMPLETENESS_QUARANTINED,
    OPPONENT_DIFFICULTY_CONTRACT,
    ROTATION_SHOCK_CONTRACT,
    SCHEDULE_PRESSURE_CONTRACT,
    STYLE_COLLISION_EDGE_CATALOG,
    STYLE_COLLISION_MAP_CONTRACT,
    OpponentDifficultyObservation,
    RotationShockObservation,
    RotationShockPlayerObservation,
    SchedulePressureObservation,
    build_opponent_difficulty_prototype,
    build_opponent_difficulty_scaled_prototype,
    build_schedule_pressure_prototype,
    build_style_collision_pace_prototype,
    calculate_schedule_pressure,
    calculate_pregame_percentile,
    calculate_rotation_shock,
    calculate_style_collision_pace,
)


UTC = timezone.utc


def _observation(**overrides) -> SchedulePressureObservation:
    values = {
        "game_id": "0022500001",
        "team_id": 1,
        "season": "2025-26",
        "season_type": "Regular Season",
        "feature_as_of": datetime(2025, 11, 10, 15, tzinfo=UTC),
        "data_available_at": datetime(2025, 11, 10, 12, tzinfo=UTC),
        "days_rest": 1,
        "opponent_days_rest": 2,
        "rest_diff": -1,
        "is_b2b": False,
        "is_3_in_4": True,
        "is_4_in_5": False,
        "is_5_in_7": False,
        "games_last_4": 2,
        "games_last_7": 2,
    }
    values.update(overrides)
    return SchedulePressureObservation(**values)


def test_contract_declares_the_program_e_gate_metadata():
    SCHEDULE_PRESSURE_CONTRACT.validate()
    assert SCHEDULE_PRESSURE_CONTRACT.version == "schedule-pressure-v0.1"
    assert "data_available_at" in SCHEDULE_PRESSURE_CONTRACT.required_inputs
    assert SCHEDULE_PRESSURE_CONTRACT.prohibited_uses


def test_opponent_difficulty_contract_declares_raw_unit_scope():
    OPPONENT_DIFFICULTY_CONTRACT.validate()
    assert OPPONENT_DIFFICULTY_CONTRACT.version == "opponent-difficulty-v0.1"
    assert "opponent_net_rtg_lastn" in OPPONENT_DIFFICULTY_CONTRACT.required_inputs
    assert "0-100" in OPPONENT_DIFFICULTY_CONTRACT.validation_range


def test_style_collision_catalog_separates_supported_and_blocked_edges():
    STYLE_COLLISION_MAP_CONTRACT.validate()
    supported = [edge for edge in STYLE_COLLISION_EDGE_CATALOG if edge.status == "supported"]
    blocked = [edge for edge in STYLE_COLLISION_EDGE_CATALOG if edge.status == "blocked"]

    assert len(supported) == 1
    assert supported[0].edge_id == "pace_preference_interaction"
    assert len(blocked) == 7
    assert "allowance" in blocked[1].limitation.lower()


def test_style_collision_pace_uses_paired_values_and_prior_reference_only():
    result = calculate_style_collision_pace(
        102.0,
        98.0,
        [float(value) for value in range(90, 110)],
        minimum_reference_size=20,
    )

    assert result.status == COMPLETENESS_COMPLETE
    assert result.home_value == 102.0
    assert result.away_value == 98.0
    assert result.combined_value == 100.0
    assert result.contrast == 4.0
    assert result.combined_percentile == 52.5
    assert "possessions per game" in result.explanation


def test_style_collision_pace_withholds_small_reference_pool():
    result = calculate_style_collision_pace(100.0, 101.0, [99.0])

    assert result.status == COMPLETENESS_PARTIAL
    assert result.combined_value == 100.5
    assert result.combined_percentile is None
    assert result.missing_inputs == ("insufficient_reference_history",)


def test_style_collision_pace_wording_supports_three_review_styles():
    result = calculate_style_collision_pace(
        102.0,
        98.0,
        [float(value) for value in range(90, 110)],
        minimum_reference_size=20,
    )
    prototypes = [
        build_style_collision_pace_prototype(
            result,
            style=style,
            home_name="Denver",
            away_name="Oklahoma City",
        )
        for style in ("raw_plus_percentile", "percentile_first", "compact")
    ]

    assert all(prototype.status == COMPLETENESS_COMPLETE for prototype in prototypes)
    assert "102.0" in prototypes[0].detail
    assert "53rd percentile" in prototypes[1].detail
    assert "Recent pace:" in prototypes[2].detail
    assert all("not a prediction of the game's final pace" in prototype.caveat for prototype in prototypes)


def test_style_collision_pace_wording_preserves_partial_state():
    result = calculate_style_collision_pace(100.0, 101.0, [99.0])
    prototype = build_style_collision_pace_prototype(result, home_name="Denver")

    assert prototype.status == COMPLETENESS_PARTIAL
    assert "percentile comparison is withheld" in prototype.detail


def _rotation_observation(**overrides) -> RotationShockObservation:
    values = {
        "game_id": "0022500001",
        "team_id": 1,
        "season": "2025-26",
        "season_type": "Regular Season",
        "feature_as_of": datetime(2025, 11, 10, 15, tzinfo=UTC),
        "data_available_at": datetime(2025, 11, 10, 12, tzinfo=UTC),
        "scheduled_tipoff": datetime(2025, 11, 10, 19, tzinfo=UTC),
        "availability_evidence_status": "complete",
        "players": (
            RotationShockPlayerObservation(
                player_id=10,
                player_name="Out Player",
                status="Out",
                prior_minutes=24.0,
                prior_usage_percentage=25.0,
                prior_assist_percentage=18.0,
                report_published_at=datetime(2025, 11, 10, 11, tzinfo=UTC),
            ),
            RotationShockPlayerObservation(
                player_id=11,
                player_name="Questionable Player",
                status="Questionable",
                prior_minutes=12.0,
                prior_usage_percentage=15.0,
                prior_assist_percentage=10.0,
                report_published_at=datetime(2025, 11, 10, 11, tzinfo=UTC),
            ),
        ),
    }
    values.update(overrides)
    return RotationShockObservation(**values)


def test_rotation_shock_contract_and_research_proxy_are_replayable():
    ROTATION_SHOCK_CONTRACT.validate()
    first = calculate_rotation_shock(_rotation_observation())
    replay = calculate_rotation_shock(_rotation_observation())

    assert first.completeness_status == COMPLETENESS_COMPLETE
    assert first.value == 12.5
    assert first.as_dict() == replay.as_dict()
    assert first.components[3] == ("weighted_minutes_at_risk", 30.0)
    assert "not estimate replacement performance" in " ".join(first.explanation)


def test_rotation_shock_withholds_missing_role_baseline_and_late_status():
    player = RotationShockPlayerObservation(
        player_id=10,
        player_name="Out Player",
        status="Out",
        prior_minutes=None,
        prior_usage_percentage=25.0,
        prior_assist_percentage=18.0,
        report_published_at=datetime(2025, 11, 10, 11, tzinfo=UTC),
    )
    missing = calculate_rotation_shock(_rotation_observation(players=(player,)))
    assert missing.completeness_status == COMPLETENESS_PARTIAL
    assert "player_10.prior_minutes" in missing.missing_inputs

    late_player = RotationShockPlayerObservation(
        player_id=10,
        player_name="Out Player",
        status="Out",
        prior_minutes=24.0,
        prior_usage_percentage=25.0,
        prior_assist_percentage=18.0,
        report_published_at=datetime(2025, 11, 10, 16, tzinfo=UTC),
    )
    late = calculate_rotation_shock(_rotation_observation(players=(late_player,)))
    assert late.completeness_status == COMPLETENESS_AFTER_CUTOFF


def test_complete_calculation_is_bounded_and_replayable():
    first = calculate_schedule_pressure(_observation())
    replay = calculate_schedule_pressure(_observation())

    assert first.completeness_status == COMPLETENESS_COMPLETE
    assert 0 <= first.value <= 100
    assert first.as_dict() == replay.as_dict()
    assert "3-in-4 schedule" in first.explanation


def test_missing_inputs_are_visible_and_not_zero_filled():
    result = calculate_schedule_pressure(_observation(days_rest=None))

    assert result.completeness_status == COMPLETENESS_PARTIAL
    assert result.value is None
    assert result.components == ()
    assert result.missing_inputs == ("days_rest",)


def test_post_cutoff_input_is_rejected():
    result = calculate_schedule_pressure(
        _observation(data_available_at=datetime(2025, 11, 10, 16, tzinfo=UTC))
    )

    assert result.completeness_status == COMPLETENESS_AFTER_CUTOFF
    assert result.value is None
    assert "data_available_at_after_feature_as_of" in result.missing_inputs


def test_inconsistent_source_flags_are_quarantined():
    result = calculate_schedule_pressure(_observation(is_3_in_4=False))

    assert result.completeness_status == COMPLETENESS_QUARANTINED
    assert result.value is None
    assert "is_3_in_4_inconsistent" in result.missing_inputs


def test_more_schedule_stress_cannot_lower_the_candidate_score():
    rested = calculate_schedule_pressure(
        _observation(
            days_rest=3,
            opponent_days_rest=3,
            rest_diff=0,
            is_b2b=False,
            is_3_in_4=False,
            games_last_4=0,
            games_last_7=0,
        )
    )
    stressed = calculate_schedule_pressure(
        _observation(
            days_rest=0,
            opponent_days_rest=3,
            rest_diff=-3,
            is_b2b=True,
            is_3_in_4=True,
            is_5_in_7=True,
            games_last_4=2,
            games_last_7=4,
        )
    )

    assert rested.completeness_status == COMPLETENESS_COMPLETE
    assert stressed.completeness_status == COMPLETENESS_COMPLETE
    assert stressed.value > rested.value


def test_user_language_prototype_explains_drivers_without_predictive_claims():
    result = calculate_schedule_pressure(_observation())
    prototype = build_schedule_pressure_prototype(
        _observation(),
        result,
        team_name="Boston",
        opponent_name="Oklahoma City",
    )

    assert prototype.status == COMPLETENESS_COMPLETE
    assert prototype.label == "Elevated schedule strain"
    assert "Schedule context for Boston" in prototype.detail
    assert "3 games in 4 days" in prototype.detail
    assert "1 fewer rest day than Oklahoma City" in prototype.detail
    assert "not a prediction" in prototype.caveat
    assert "Opponent strength and travel are not included" in prototype.caveat
    assert prototype.as_dict()["drivers"] == list(prototype.drivers)


def test_user_language_prototype_uses_neutral_band_labels_and_drivers():
    cases = (
        (
            _observation(
                days_rest=3,
                opponent_days_rest=3,
                rest_diff=0,
                is_3_in_4=False,
                games_last_4=0,
                games_last_7=0,
            ),
            "Low schedule strain",
        ),
        (
            _observation(
                days_rest=1,
                opponent_days_rest=1,
                rest_diff=0,
                is_3_in_4=False,
                games_last_4=1,
                games_last_7=2,
            ),
            "Moderate schedule strain",
        ),
        (
            _observation(
                days_rest=1,
                opponent_days_rest=1,
                rest_diff=0,
                is_b2b=False,
                is_3_in_4=True,
                games_last_4=2,
                games_last_7=2,
            ),
            "Elevated schedule strain",
        ),
        (
            _observation(
                days_rest=0,
                opponent_days_rest=3,
                rest_diff=-3,
                is_b2b=True,
                is_3_in_4=True,
                is_5_in_7=True,
                games_last_4=2,
                games_last_7=4,
            ),
            "High schedule strain",
        ),
    )

    for observation, expected_label in cases:
        result = calculate_schedule_pressure(observation)
        prototype = build_schedule_pressure_prototype(observation, result)
        assert prototype.label == expected_label

    observation = _observation(
        days_rest=0,
        opponent_days_rest=0,
        rest_diff=0,
        is_b2b=True,
        is_3_in_4=True,
        games_last_4=2,
        games_last_7=2,
    )
    prototype = build_schedule_pressure_prototype(
        observation,
        calculate_schedule_pressure(observation),
    )
    assert "playing back-to-back games" in prototype.drivers


def test_user_language_prototype_preserves_unavailable_state():
    observation = _observation(days_rest=None)
    result = calculate_schedule_pressure(observation)
    prototype = build_schedule_pressure_prototype(observation, result, team_name="Boston")

    assert prototype.status == COMPLETENESS_PARTIAL
    assert prototype.label == "Unavailable"
    assert prototype.drivers == ()
    assert "history is incomplete" in prototype.detail


def test_opponent_difficulty_prototype_keeps_target_and_sos_separate():
    observation = OpponentDifficultyObservation(
        game_id="0022500001",
        team_id=1,
        season="2025-26",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 11, 10, 15, tzinfo=UTC),
        data_available_at=datetime(2025, 11, 10, 12, tzinfo=UTC),
        opponent_net_rtg_season=7.25,
        opponent_net_rtg_lastn=8.5,
        team_sos_net_season=2.1,
        team_sos_net_lastn=3.4,
    )

    prototype = build_opponent_difficulty_prototype(
        observation,
        team_name="Boston",
        opponent_name="Oklahoma City",
    )

    assert prototype.status == COMPLETENESS_COMPLETE
    assert prototype.headline == "Boston: opponent difficulty context"
    assert "Oklahoma City" in prototype.detail
    assert "+8.5" in prototype.detail
    assert "+3.4" in prototype.detail
    assert "posted a net rating" in prototype.detail
    assert "previous opponents for Boston averaged" in prototype.detail
    assert "Higher values indicate stronger opponents" in prototype.detail
    assert "not a performance or outcome prediction" in prototype.caveat


def test_opponent_difficulty_prototype_preserves_missing_state():
    observation = OpponentDifficultyObservation(
        game_id="0022500001",
        team_id=1,
        season="2025-26",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 11, 10, 15, tzinfo=UTC),
        data_available_at=datetime(2025, 11, 10, 12, tzinfo=UTC),
        opponent_net_rtg_season=None,
        opponent_net_rtg_lastn=8.5,
        team_sos_net_season=2.1,
        team_sos_net_lastn=3.4,
    )

    prototype = build_opponent_difficulty_prototype(observation, team_name="Boston")

    assert prototype.status == COMPLETENESS_PARTIAL
    assert prototype.drivers == ()
    assert "required pregame strength inputs are incomplete" in prototype.detail


def test_pregame_percentile_requires_prior_reference_history():
    result = calculate_pregame_percentile(4.0, [1.0, 2.0, 3.0], minimum_reference_size=4)

    assert result.completeness_status == COMPLETENESS_PARTIAL
    assert result.percentile is None
    assert result.reference_size == 3
    assert result.missing_inputs == ("insufficient_reference_history",)


def test_pregame_percentile_is_bounded_tie_aware_and_replayable():
    values = [1.0, 2.0, 2.0, 3.0]
    first = calculate_pregame_percentile(2.0, values, minimum_reference_size=2)
    replay = calculate_pregame_percentile(2.0, values, minimum_reference_size=2)

    assert first.completeness_status == COMPLETENESS_COMPLETE
    assert first.percentile == 50.0
    assert first.rank == 2.5
    assert 0 <= first.percentile <= 100
    assert first.as_dict() == replay.as_dict()


def test_pregame_percentile_withholds_missing_and_non_finite_values():
    missing = calculate_pregame_percentile(None, [1.0, 2.0])
    invalid = calculate_pregame_percentile(float("nan"), [1.0, 2.0])

    assert missing.missing_inputs == ("value_missing",)
    assert invalid.completeness_status == COMPLETENESS_QUARANTINED
    assert invalid.missing_inputs == ("value_not_finite",)


def test_scaled_opponent_prototype_supports_three_wording_styles():
    observation = OpponentDifficultyObservation(
        game_id="0022500001",
        team_id=1,
        season="2025-26",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 11, 10, 15, tzinfo=UTC),
        data_available_at=datetime(2025, 11, 10, 12, tzinfo=UTC),
        opponent_net_rtg_season=12.1,
        opponent_net_rtg_lastn=21.8,
        team_sos_net_season=-0.3,
        team_sos_net_lastn=-1.9,
    )
    common = {
        "opponent_season_percentile": 82.0,
        "opponent_recent_percentile": 94.0,
        "team_sos_season_percentile": 47.0,
        "team_sos_recent_percentile": 42.0,
        "team_name": "Denver Nuggets",
        "opponent_name": "Oklahoma City Thunder",
    }

    prototypes = [
        build_opponent_difficulty_scaled_prototype(observation, style=style, **common)
        for style in ("raw_plus_percentile", "percentile_first", "compact")
    ]

    assert all(prototype.status == COMPLETENESS_COMPLETE for prototype in prototypes)
    assert "+12.1" in prototypes[0].detail
    assert "82nd percentile" in prototypes[0].detail
    assert "94th percentile" in prototypes[1].detail
    assert "Matchup context for Denver Nuggets vs. Oklahoma City Thunder" in prototypes[2].detail
    assert all("not a performance or outcome prediction" in prototype.caveat for prototype in prototypes)


def test_scaled_opponent_prototype_rejects_invalid_percentile():
    observation = OpponentDifficultyObservation(
        game_id="0022500001",
        team_id=1,
        season="2025-26",
        season_type="Regular Season",
        feature_as_of=datetime(2025, 11, 10, 15, tzinfo=UTC),
        data_available_at=datetime(2025, 11, 10, 12, tzinfo=UTC),
        opponent_net_rtg_season=1.0,
        opponent_net_rtg_lastn=2.0,
        team_sos_net_season=3.0,
        team_sos_net_lastn=4.0,
    )

    prototype = build_opponent_difficulty_scaled_prototype(
        observation,
        opponent_season_percentile=101.0,
        opponent_recent_percentile=50.0,
        team_sos_season_percentile=50.0,
        team_sos_recent_percentile=50.0,
    )

    assert prototype.status == COMPLETENESS_QUARANTINED
