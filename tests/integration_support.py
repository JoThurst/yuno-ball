"""Disposable ORM-schema fixtures, never a production migration/bootstrap tool."""
import importlib
from pathlib import Path


def validate_ephemeral_target(url, environ):
    if (environ.get('YUNOBALL_EPHEMERAL_TEST_DB') != '1'
            or url.get_backend_name() != 'postgresql'
            or url.host not in {'localhost', '127.0.0.1', '::1'}
            or url.database != 'yunoball_test' or url.query
            or any(environ.get(key) for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE'))):
        raise ValueError('Fixture setup requires an explicitly opted-in loopback yunoball_test database')


def bootstrap_ephemeral_database():
    import os
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import inspect, text
    from sqlalchemy.orm import Session
    from app.database import Base, engine
    from app.utils.season_utils import get_current_season

    validate_ephemeral_target(engine.url, os.environ)
    for module in sorted((Path(__file__).resolve().parents[1] / 'app' / 'models').glob('*_sqlalchemy.py')):
        importlib.import_module(f'app.models.{module.stem}')
    from app.models.team_sqlalchemy import TeamORM, RosterORM
    from app.models.player_sqlalchemy import PlayerORM
    from app.models.gamelog_sqlalchemy import GameLogORM
    from app.models.gameschedule_sqlalchemy import GameScheduleORM
    from app.models.team_game_stats_sqlalchemy import TeamGameStatsORM
    from app.models.statistics_sqlalchemy import StatisticsORM
    from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
    from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM

    with engine.begin() as connection:
        if connection.execute(text('select current_database()')).scalar_one() != 'yunoball_test':
            raise ValueError('Unexpected test database')
        if inspect(connection).get_table_names(schema='public'):
            raise ValueError('Fixture setup refuses a nonempty database; use a fresh disposable service')
        Base.metadata.create_all(connection)
        season = get_current_season()
        with Session(bind=connection) as db:
            db.add_all([TeamORM(team_id=10, name='Fixture East', abbreviation='FXE'),
                        TeamORM(team_id=20, name='Fixture West', abbreviation='FXW'),
                        PlayerORM(player_id=101, name='Fixture Player One', available_seasons=[season]),
                        PlayerORM(player_id=102, name='Fixture Player Two', available_seasons=[season])])
            db.flush()
            tip = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
            for team, opponent, side, result, points, opponent_points in (
                    (10, 20, 'H', 'W', 100, 90), (20, 10, 'A', 'L', 90, 100)):
                db.add(GameScheduleORM(game_id='fixture-game', team_id=team,
                    opponent_team_id=opponent, season=season, season_type='Regular Season',
                    game_date=tip, game_date_precision='exact', home_or_away=side,
                    result=result, team_score=points, opponent_score=opponent_points,
                    source_name='synthetic-test-fixture'))
                db.add(TeamGameStatsORM(game_id='fixture-game', team_id=team,
                    opponent_team_id=opponent, season=season, game_date=tip.date(),
                    pts=points, wl=result, plus_minus=points-opponent_points))
            db.flush()
            for player, team in ((101, 10), (102, 20)):
                db.add(RosterORM(team_id=team, player_id=player, season=season, player_name=f'Fixture {player}'))
                db.add(StatisticsORM(player_id=player, season_year=season, points=20, rebounds=5, assists=4))
                db.add(LeagueDashPlayerStatsORM(player_id=player, season=season, team_id=team,
                                               pts=20, reb=5, ast=4, gp=1))
                db.add(GameLogORM(player_id=player, game_id='fixture-game', team_id=team,
                                 season=season, points=20, rebounds=5, assists=4, minutes_played='20.0'))
            for team, name in ((10, 'Fixture East'), (20, 'Fixture West')):
                db.add(LeagueDashTeamStatsORM(team_id=team, team_name=name, season=season,
                                             season_type='Regular Season', base_totals_gp=1,
                                             base_totals_w=1, base_totals_l=0))
            db.flush()
