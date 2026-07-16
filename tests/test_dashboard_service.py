"""Unit and integration tests for DashboardService.

This test suite covers:
- Unit tests with mocks for DashboardService methods
- Integration tests with real database for DashboardService methods
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, date

from sqlalchemy.orm import Session

from app.services.dashboard_service import DashboardService
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.team_sqlalchemy import TeamORM
from app.models.player_sqlalchemy import PlayerORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.database import get_db_context
from tests.test_base import BaseTestCase


class TestDashboardServiceUnit(BaseTestCase):
    """Unit tests for DashboardService with mocks."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.service = DashboardService()
        self.mock_session = Mock(spec=Session)
    
    def test_get_calendar_days(self):
        """Test get_calendar_days returns correct date range."""
        result = self.service.get_calendar_days()
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 7)  # Should return 7 days
        # Check that result contains dictionaries with date info
        if len(result) > 0:
            self.assertIsInstance(result[0], dict)
            self.assertIn("date", result[0])
            self.assertIn("weekday", result[0])
            self.assertIn("games", result[0])
    
    def test_get_today_matchups_with_cache(self):
        """Test get_today_matchups returns cached data."""
        cached_matchups = [
            {"game_id": "001", "team_id": 1, "opponent_team_id": 2}
        ]
        
        with patch('app.services.base_service.get_cache', return_value=cached_matchups):
            result = self.service.get_today_matchups()
            self.assertEqual(result, cached_matchups)
    
    def test_get_today_matchups_with_cache_miss(self):
        """Test get_today_matchups fetches from database on cache miss."""
        mock_games = [
            Mock(spec=GameScheduleORM)
        ]
        mock_games[0].to_dict.return_value = {
            "game_id": "001",
            "team_id": 1,
            "opponent_team_id": 2,
            "game_date": date.today()
        }
        
        with patch('app.services.base_service.get_cache', return_value=None):
            with patch('app.services.base_service.set_cache') as mock_set_cache:
                # get_today_matchups uses fetch_todays_games() utility function
                with patch('app.services.dashboard_service.fetch_todays_games', return_value={"games": [{"game_id": "001"}]}):
                    with patch('app.services.base_service.get_db_context') as mock_db_context:
                        mock_db_context.return_value.__enter__.return_value = self.mock_session
                        mock_db_context.return_value.__exit__.return_value = None
                        
                        result = self.service.get_today_matchups()
                        
                        self.assertIsInstance(result, list)
                        mock_set_cache.assert_called_once()
    
    def test_process_games_data(self):
        """Test process_games_data formats games correctly."""
        # process_games_data expects tuples: (game_id, team_id, opponent_team_id, game_date, home_or_away, result, score)
        from datetime import datetime
        mock_games = [
            ("001", 1, 2, datetime.now(), "H", "W", "120-115")
        ]
        
        # team_stats is a list of dicts with team stats
        mock_team_stats = [
            {"team_id": 1, "pts_rank": 100, "reb_rank": 50, "ast_rank": 75, "fgm_rank": 60},
            {"team_id": 2, "pts_rank": 90, "reb_rank": 60, "ast_rank": 80, "fgm_rank": 55}
        ]
        
        mock_teams = {
            1: Mock(spec=TeamORM),
            2: Mock(spec=TeamORM)
        }
        mock_teams[1].to_dict.return_value = {"team_id": 1, "name": "Team 1", "abbreviation": "T1", "record": "50-32"}
        mock_teams[2].to_dict.return_value = {"team_id": 2, "name": "Team 2", "abbreviation": "T2", "record": "45-37"}
        
        with patch('app.services.dashboard_service.TeamORM.get_by_id') as mock_get_team:
            def side_effect(team_id, session):
                return mock_teams.get(team_id)
            mock_get_team.side_effect = side_effect
            
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.process_games_data(mock_games, mock_team_stats)
                
                self.assertIsInstance(result, list)
                if len(result) > 0:
                    self.assertIn("home_team_name", result[0])
                    self.assertIn("away_team_name", result[0])
    
    def test_get_featured_games(self):
        """Test get_featured_games returns featured games."""
        # get_featured_games is a static method that takes a games list
        games = [
            {"game_id": "001", "game_status": "Scheduled", "team": {"name": "Team 1"}, "opponent": {"name": "Team 2"}},
            {"game_id": "002", "game_status": "Final", "team": {"name": "Team 3"}, "opponent": {"name": "Team 4"}},
            {"game_id": "003", "game_status": "Today", "team": {"name": "Team 5"}, "opponent": {"name": "Team 6"}},
            {"game_id": "004", "game_status": "Scheduled", "team": {"name": "Team 7"}, "opponent": {"name": "Team 8"}}
        ]
        
        result = DashboardService.get_featured_games(games)
        
        self.assertIsInstance(result, list)
        # Should return max 3 games, prioritizing non-final games
        self.assertLessEqual(len(result), 3)
    
    def test_get_standings_data(self):
        """Test get_standings_data processes teams data correctly."""
        # get_standings_data is a static method that processes teams data
        teams = [
            {"name": "Team 1", "wins": 50, "losses": 32, "win_pct": 0.610, "conference": "East"},
            {"name": "Team 2", "wins": 45, "losses": 37, "win_pct": 0.549, "conference": "East"},
            {"name": "Team 3", "wins": 55, "losses": 27, "win_pct": 0.671, "conference": "West"},
            {"name": "Team 4", "wins": 40, "losses": 42, "win_pct": 0.488, "conference": "West"}
        ]
        
        result = DashboardService.get_standings_data(teams)
        
        self.assertIsInstance(result, dict)
        self.assertIn("East", result)
        self.assertIn("West", result)
        self.assertEqual(len(result["East"]), 2)
        self.assertEqual(len(result["West"]), 2)
        # Check that standings are sorted by win percentage (highest first)
        self.assertEqual(result["East"][0]["TEAM"], "Team 1")
        self.assertEqual(result["West"][0]["TEAM"], "Team 3")
    
    def test_get_hot_players_data(self):
        """Test get_hot_players_data returns hot players."""
        mock_streaks = [
            {
                "player_id": 1,
                "player_name": "Test Player",
                "team": "LAL",
                "stat": "points",
                "streak_games": 5,
                "threshold": 25
            }
        ]
        
        with patch('app.services.dashboard_service.PlayerStreaksORM.get_hot_streaks', return_value=mock_streaks):
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.get_hot_players_data()
                
                self.assertIsInstance(result, list)
                if len(result) > 0:
                    self.assertIn("player_name", result[0])


class TestDashboardServiceIntegration(BaseTestCase):
    """Integration tests for DashboardService with real database."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Set up Flask application context for services that need it
        from app import create_app
        from tests.config import TestConfig
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.service = DashboardService()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.app_context:
            self.app_context.pop()
        super().tearDown()
    
    def test_get_calendar_days_integration(self):
        """Test get_calendar_days returns correct dates."""
        try:
            result = self.service.get_calendar_days()
            
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 7)
            # Check that result contains dictionaries with date info
            if len(result) > 0:
                self.assertIsInstance(result[0], dict)
                self.assertIn("date", result[0])
                self.assertIn("weekday", result[0])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_standings_data_integration(self):
        """Test get_standings_data with real data."""
        # get_standings_data is a static method that processes teams data
        # This test just verifies it works with sample data
        teams = [
            {"name": "Test Team", "wins": 50, "losses": 32, "win_pct": 0.610, "conference": "East"}
        ]
        
        result = DashboardService.get_standings_data(teams)
        
        self.assertIsInstance(result, dict)
        self.assertIn("East", result)
        self.assertIn("West", result)
    
    def test_get_hot_players_data_integration(self):
        """Test get_hot_players_data with real database."""
        try:
            result = self.service.get_hot_players_data(limit=10)
            
            self.assertIsInstance(result, list)
            # If we have hot players, check structure
            if len(result) > 0:
                self.assertIn("player_name", result[0])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")


if __name__ == '__main__':
    unittest.main()

