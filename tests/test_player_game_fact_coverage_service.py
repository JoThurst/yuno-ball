from datetime import date, datetime

from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_game_fact_sqlalchemy import (
    PlayerGameAdvancedFactORM,
    PlayerGameFactORM,
)
from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
from app.services.player_game_fact_coverage_service import (
    build_player_game_fact_coverage_report,
)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, mapping):
        self.mapping = mapping

    def query(self, model):
        return FakeQuery(self.mapping.get(model, []))


def schedule(game_id, team_id, opponent, result):
    return GameScheduleORM(
        game_id=game_id,
        team_id=team_id,
        opponent_team_id=opponent,
        season="2025-26",
        season_type="Regular Season",
        game_date=datetime(2026, 3, 3),
        game_date_precision="exact",
        home_or_away="H" if team_id == 1 else "A",
        result=result,
        source_name="test",
    )


def test_inventory_identifies_missing_sequential_fact_coverage():
    db = FakeDB(
        {
            GameScheduleORM: [schedule("g1", 1, 2, "W"), schedule("g1", 2, 1, "L")],
            TeamGameStatsORM: [
                TeamGameStatsORM(game_id="g1", team_id=1, opponent_team_id=2, season="2025-26", game_date=date(2026, 3, 3)),
                TeamGameStatsORM(game_id="g1", team_id=2, opponent_team_id=1, season="2025-26", game_date=date(2026, 3, 3)),
            ],
            PlayerGameFactORM: [],
            PlayerGameAdvancedFactORM: [],
        }
    )
    report = build_player_game_fact_coverage_report(db, season="2025-26", season_type="Regular Season")
    assert report["eligible_completed_games"] == 1
    assert report["traditional_missing_games"] == 1
    assert report["advanced_missing_games"] == 1
    assert report["team_stats_game_ids"] == 1
    assert report["traditional_backfill_batches"] == [["g1"]]


def test_inventory_does_not_count_empty_stats_defaultdict_entries():
    db = FakeDB(
        {
            GameScheduleORM: [schedule("g1", 1, 2, "W"), schedule("g1", 2, 1, "L")],
            TeamGameStatsORM: [],
            PlayerGameFactORM: [],
            PlayerGameAdvancedFactORM: [],
        }
    )

    report = build_player_game_fact_coverage_report(
        db,
        season="2025-26",
        season_type="Regular Season",
    )

    assert report["team_stats_game_ids"] == 0
    assert report["blocked_games"] == 1


def test_inventory_marks_covered_games_and_caps_batches():
    schedule_rows = []
    stats_rows = []
    traditional_rows = []
    advanced_rows = []
    for index in range(26):
        game_id = f"g{index}"
        schedule_rows.extend([schedule(game_id, 1, 2, "W"), schedule(game_id, 2, 1, "L")])
        stats_rows.extend([
            TeamGameStatsORM(game_id=game_id, team_id=1, opponent_team_id=2, season="2025-26", game_date=date(2026, 3, 3)),
            TeamGameStatsORM(game_id=game_id, team_id=2, opponent_team_id=1, season="2025-26", game_date=date(2026, 3, 3)),
        ])
    traditional_rows.append(PlayerGameFactORM(canonical_game_id="g0", season="2025-26", season_type="Regular Season"))
    advanced_rows.append(PlayerGameAdvancedFactORM(canonical_game_id="g0", season="2025-26", season_type="Regular Season"))
    db = FakeDB({GameScheduleORM: schedule_rows, TeamGameStatsORM: stats_rows, PlayerGameFactORM: traditional_rows, PlayerGameAdvancedFactORM: advanced_rows})
    report = build_player_game_fact_coverage_report(db, season="2025-26", season_type="Regular Season", max_batch_size=25)
    assert report["traditional_covered_games"] == 1
    assert [len(batch) for batch in report["traditional_backfill_batches"]] == [25]
