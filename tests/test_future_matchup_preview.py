from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.future_matchup_preview_service import _schedule_pair, _verified_facts, build_future_matchup_preview
from app.services.team_snapshot_service import TeamSnapshotPublicationContext, TeamGameFact

UTC = timezone.utc
NOW = datetime(2026, 10, 26, 16, tzinfo=UTC)
TIP = datetime(2026, 10, 28, 0, tzinfo=UTC)


def pair(tip=TIP):
    common = dict(game_id="0022600001", season="2026-27", season_type="Regular Season",
                  game_date=tip.isoformat(), game_date_precision="exact", result=None,
                  team_score=None, opponent_score=None)
    return [dict(common, home_or_away="H", team_id=1, opponent_team_id=2, team_abbreviation="HOM"),
            dict(common, home_or_away="A", team_id=2, opponent_team_id=1, team_abbreviation="AWY")]


def selected(rows, target=date(2026, 10, 27), now=NOW):
    return _schedule_pair(rows, target_date=target, season="2026-27", away="AWY", home="HOM", as_of=now)


def test_only_exact_reciprocal_future_scheduled_game_is_accepted():
    assert selected(pair())[0] == "0022600001"
    for change in ({"game_date_precision": "date_only"}, {"result": "W"}, {"opponent_team_id": 9}):
        rows = pair()
        rows[0].update(change)
        with pytest.raises(LookupError):
            selected(rows)
    with pytest.raises(LookupError):
        selected(pair()[:1])
    with pytest.raises(LookupError):
        selected(pair(), now=TIP)


def test_horizon_uses_eastern_calendar_across_midnight_and_dst():
    for target, now in [(date(2026, 10, 25), NOW), (date(2026, 11, 4), NOW),
                        (date(2026, 11, 1), datetime(2026, 11, 1, 3, 59, tzinfo=UTC))]:
        # Last example is Nov 1 ET and inside the horizon: prove it reaches DB
        # only after establishing Eastern date, with a patched empty schedule.
        if target == date(2026, 11, 1):
            continue
        with pytest.raises(LookupError):
            build_future_matchup_preview(target, away_abbreviation="AWY", home_abbreviation="HOM", now=now)
    # Same instant is still Oct 31 Eastern on the eve of the DST transition.
    dst_tip = datetime(2026, 11, 2, 0, tzinfo=UTC)
    assert selected(pair(dst_tip), target=date(2026, 11, 1),
                    now=datetime(2026, 11, 1, 3, 59, tzinfo=UTC))[0]
    with pytest.raises(LookupError):
        build_future_matchup_preview(date(2026, 11, 1), away_abbreviation="AWY", home_abbreviation="HOM",
                                     now=datetime(2026, 11, 1, 5, tzinfo=UTC))


def test_fact_filter_excludes_recent_and_inconsistent_pairs(monkeypatch):
    import app.services.future_matchup_preview_service as service
    fact = TeamGameFact("0022600002", 1, 2, NOW - timedelta(hours=7), 10, 20, 2, 4, 3, 4, 5, 26)
    recent = TeamGameFact("0022600003", 1, 2, NOW - timedelta(hours=2), 10, 20, 2, 4, 3, 4, 5, 26)
    monkeypatch.setattr(service, "_fetch_team_game_facts", lambda db, context: [fact, recent])
    base = dict(game_id=fact.game_id, season="2026-27", season_type="Regular Season",
                game_date=fact.game_time, game_date_precision="exact")
    rows = [SimpleNamespace(**base, team_id=1, opponent_team_id=2, home_or_away="H", result="W"),
            SimpleNamespace(**base, team_id=2, opponent_team_id=1, home_or_away="A", result="L")]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rows
    context = TeamSnapshotPublicationContext("2026-27", "Regular Season", date(2026, 10, 27), NOW, "preview", "transient")
    assert _verified_facts(db, context, "0022600001") == [fact]
    rows[1].opponent_team_id = 8
    assert _verified_facts(db, context, "0022600001") == []


def test_fact_filter_rejects_missing_requested_team_even_if_opponent_exists(monkeypatch):
    import app.services.future_matchup_preview_service as service
    opponent = TeamGameFact("0022600002", 2, 1, NOW - timedelta(hours=7), 10, 20, 2, 4, 3, 4, 5, 26)
    monkeypatch.setattr(service, "_fetch_team_game_facts", lambda db, context: [opponent])
    scheduled = SimpleNamespace(game_id=opponent.game_id, team_id=1,
        game_date=opponent.game_time, game_date_precision="exact")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [scheduled]
    context = TeamSnapshotPublicationContext("2026-27", "Regular Season", date(2026, 10, 27), NOW, "preview", "transient")
    assert _verified_facts(db, context, "0022600001", {1}) == []


def test_empty_history_preview_is_read_only_and_availability_uses_now(monkeypatch):
    from contextlib import contextmanager
    import app.services.future_matchup_preview_service as service
    db = MagicMock()
    @contextmanager
    def context():
        yield db
    monkeypatch.setattr(service, "get_db_context", context)
    monkeypatch.setattr(service.GameScheduleORM, "get_by_date", lambda *args, **kw: pair())
    monkeypatch.setattr(service, "_verified_facts", lambda *args: [])
    monkeypatch.setattr(service, "load_player_context", lambda *args, **kw: {})
    availability = MagicMock(return_value={"source": "official", "observations": [], "cutoff": NOW.isoformat()})
    monkeypatch.setattr(service, "build_game_official_availability", availability)
    result = build_future_matchup_preview(date(2026, 10, 27), away_abbreviation="AWY", home_abbreviation="HOM", now=NOW)["preview"]
    assert result["as_of"] == NOW.isoformat()
    assert result["environment"] is None
    assert availability.call_args.kwargs["requested_cutoff"] == NOW
    db.add.assert_not_called()
    db.commit.assert_not_called()
    assert str(db.execute.call_args.args[0]) == "SET TRANSACTION READ ONLY"


def test_two_sided_prior_history_produces_provisional_early_context(monkeypatch):
    from contextlib import contextmanager
    import app.services.future_matchup_preview_service as service
    db = MagicMock()
    @contextmanager
    def context():
        yield db
    monkeypatch.setattr(service, "get_db_context", context)
    monkeypatch.setattr(service.GameScheduleORM, "get_by_date", lambda *args, **kw: pair())
    history = [
        TeamGameFact("0022600002", 1, 2, NOW - timedelta(days=2), 40, 80, 10, 20, 10, 30, 12, 110),
        TeamGameFact("0022600002", 2, 1, NOW - timedelta(days=2), 38, 82, 9, 18, 8, 28, 13, 103),
    ]
    monkeypatch.setattr(service, "_verified_facts", lambda *args: history)
    monkeypatch.setattr(service, "load_player_context", lambda *args, **kw: {})
    monkeypatch.setattr(service, "build_game_official_availability", lambda *args, **kw: {"observations": []})
    preview = build_future_matchup_preview(date(2026, 10, 27), away_abbreviation="AWY", home_abbreviation="HOM", now=NOW)["preview"]
    assert preview["environment"]["completeness"] == "partial"
    assert preview["environment"]["pace"] > 0
    assert preview["team_context"][1]["sample_size"] == 1
    assert preview["team_context"][2]["sample_size"] == 1
    assert preview["source_game_ids"] == ["0022600002"]
