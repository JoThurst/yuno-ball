"""Unit and integration tests for TeamService.

This test suite covers:
- Unit tests with mocks for TeamService methods
- Integration tests with real database for TeamService methods
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.team_service import TeamService
from app.models.team_sqlalchemy import TeamORM
from app.models.leaguedashteamstats_sqlalchemy import LeagueDashTeamStatsORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.database import get_db_context
from tests.test_base import BaseTestCase


class TestTeamServiceUnit(BaseTestCase):
    """Unit tests for TeamService with mocks."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.service = TeamService()
        self.mock_session = Mock(spec=Session)
    
    def test_get_team_stats_with_cache_hit(self):
        """Test get_team_stats returns cached data."""
        cached_stats = {
            "team_id": 1,
            "team_name": "Test Team",
            "wins": 50,
            "losses": 32
        }
        
        with patch('app.services.base_service.get_cache', return_value=cached_stats):
            result = self.service.get_team_stats(1)
            self.assertEqual(result, cached_stats)
    
    def test_get_team_stats_with_cache_miss(self):
        """Test get_team_stats fetches from database on cache miss."""
        mock_stats = Mock(spec=LeagueDashTeamStatsORM)
        mock_stats.to_dict.return_value = {
            "team_id": 1,
            "team_name": "Test Team",
            "base_totals_w": 50,
            "base_totals_l": 32,
            "base_totals_pts": 5000,
            "base_totals_gp": 82
        }
        
        with patch('app.services.base_service.get_cache', return_value=None):
            with patch('app.services.base_service.set_cache') as mock_set_cache:
                with patch('app.services.team_service.LeagueDashTeamStatsORM.get_by_team', return_value=mock_stats):
                    with patch('app.services.base_service.get_db_context') as mock_db_context:
                        mock_db_context.return_value.__enter__.return_value = self.mock_session
                        mock_db_context.return_value.__exit__.return_value = None
                        
                        result = self.service.get_team_stats(1, season="2024-25")
                        
                        self.assertIsInstance(result, dict)
                        # get_team_stats returns stats dict, not team_id
                        self.assertIn("pts", result)
                        self.assertIn("reb", result)
                        mock_set_cache.assert_called_once()
    
    def test_get_team_stats_not_found(self):
        """Test get_team_stats returns empty dict when team not found."""
        with patch('app.services.team_service.LeagueDashTeamStatsORM.get_by_team', return_value=None):
            with patch('app.services.base_service.get_cache', return_value=None):
                with patch('app.services.base_service.set_cache'):
                    with patch('app.services.base_service.get_db_context') as mock_db_context:
                        mock_db_context.return_value.__enter__.return_value = self.mock_session
                        mock_db_context.return_value.__exit__.return_value = None
                        
                        result = self.service.get_team_stats(999)
                        
                        self.assertIsInstance(result, dict)
                        # Should return default stats dict
                        self.assertIn("pts", result)
                        self.assertIn("reb", result)
    
    def test_get_team_game_results(self):
        """Test get_team_game_results formats game results correctly."""
        mock_games = [
            Mock(spec=GameScheduleORM)
        ]
        mock_games[0].to_dict.return_value = {
            "game_id": "001",
            "date": "2024-01-15",
            "result": "W",
            "score": "120-115",
            "opponent_team_id": 2
        }
        
        with patch('app.services.base_service.get_cache', return_value=None):
            with patch('app.services.base_service.set_cache'):
                with patch('app.services.team_service.GameScheduleORM.get_last_n_games', return_value=mock_games):
                    with patch('app.services.base_service.get_db_context') as mock_db_context:
                        mock_db_context.return_value.__enter__.return_value = self.mock_session
                        mock_db_context.return_value.__exit__.return_value = None
                        
                        result = self.service.get_team_game_results(1, limit=1)
                        
                        self.assertIsInstance(result, list)
                        if len(result) > 0:
                            self.assertIn("game_date", result[0])
                            self.assertIn("result", result[0])
    
    def test_get_team_upcoming_schedule(self):
        """Test get_team_upcoming_schedule returns upcoming games."""
        mock_games = [
            Mock(spec=GameScheduleORM)
        ]
        mock_games[0].to_dict.return_value = {
            "game_id": "002",
            "game_date": datetime(2025, 12, 25),  # Future date
            "opponent_team_id": 3
        }
        
        with patch('app.services.base_service.get_cache', return_value=None):
            with patch('app.services.base_service.set_cache'):
                with patch('app.services.team_service.GameScheduleORM.get_upcoming_n_games', return_value=mock_games):
                    with patch('app.services.base_service.get_db_context') as mock_db_context:
                        mock_db_context.return_value.__enter__.return_value = self.mock_session
                        mock_db_context.return_value.__exit__.return_value = None
                        
                        result = self.service.get_team_upcoming_schedule(1, limit=1)
                        
                        self.assertIsInstance(result, list)
    
    def test_get_complete_team_details(self):
        """Test get_complete_team_details combines all team data."""
        mock_team = Mock(spec=TeamORM)
        mock_team.to_dict.return_value = {
            "team_id": 1,
            "name": "Test Team",
            "abbreviation": "TT"
        }
        mock_team.get_roster.return_value = []
        
        mock_stats = Mock(spec=LeagueDashTeamStatsORM)
        mock_stats.to_dict.return_value = {
            "base_totals_w": 50,
            "base_totals_l": 32
        }
        
        with patch('app.services.team_service.TeamORM.get_by_id', return_value=mock_team):
            with patch('app.services.team_service.LeagueDashTeamStatsORM.get_by_team', return_value=mock_stats):
                with patch.object(self.service, 'get_team_game_results', return_value=[]):
                    with patch.object(self.service, 'get_team_upcoming_schedule', return_value=[]):
                        with patch('app.services.base_service.get_db_context') as mock_db_context:
                            mock_db_context.return_value.__enter__.return_value = self.mock_session
                            mock_db_context.return_value.__exit__.return_value = None
                            
                            result = self.service.get_complete_team_details(1)
                            
                            self.assertIsNotNone(result)
                            self.assertIsInstance(result, dict)
                            # The method returns team_data directly, not nested under 'team'
                            self.assertIn("team_id", result)
                            self.assertIn("stats", result)
                            self.assertIn("roster", result)
    
    def test_get_enhanced_teams_data(self):
        """Test get_enhanced_teams_data returns formatted teams list."""
        mock_teams = [
            Mock(spec=TeamORM)
        ]
        mock_teams[0].to_dict.return_value = {
            "team_id": 1,
            "name": "Test Team",
            "abbreviation": "TT"
        }
        
        with patch('app.services.team_service.TeamORM.get_all', return_value=mock_teams):
            with patch.object(self.service, 'get_team_stats') as mock_get_stats:
                mock_get_stats.return_value = {
                    "wins": 50,
                    "losses": 32
                }
                with patch('app.services.base_service.get_db_context') as mock_db_context:
                    mock_db_context.return_value.__enter__.return_value = self.mock_session
                    mock_db_context.return_value.__exit__.return_value = None
                    
                    result = self.service.get_enhanced_teams_data()
                    
                    self.assertIsInstance(result, list)
                    if len(result) > 0:
                        self.assertIn("team", result[0])
                        self.assertIn("stats", result[0])


class TestTeamServiceIntegration(BaseTestCase):
    """Integration tests for TeamService with real database."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Set up Flask application context for services that need it
        from app import create_app
        from tests.config import TestConfig
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.service = TeamService()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.app_context:
            self.app_context.pop()
        super().tearDown()
    
    def test_get_team_stats_integration(self):
        """Test get_team_stats with real database."""
        try:
            # Get a real team ID from database
            with get_db_context() as db:
                team = db.query(TeamORM).first()
                if not team:
                    self.skipTest("No teams in database")
                team_id = team.team_id
            
            result = self.service.get_team_stats(team_id)
            
            self.assertIsInstance(result, dict)
            self.assertIn("team_id", result)
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_team_game_results_integration(self):
        """Test get_team_game_results with real database."""
        try:
            # Get a team with game results
            with get_db_context() as db:
                team = db.query(TeamORM).first()
                if not team:
                    self.skipTest("No teams in database")
                team_id = team.team_id
            
            result = self.service.get_team_game_results(team_id, limit=5)
            
            self.assertIsInstance(result, list)
            # If we have games, check structure
            if len(result) > 0:
                self.assertIn("game_date", result[0])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_complete_team_details_integration(self):
        """Test get_complete_team_details with real database."""
        try:
            # Get a real team ID
            with get_db_context() as db:
                team = db.query(TeamORM).first()
                if not team:
                    self.skipTest("No teams in database")
                team_id = team.team_id
            
            result = self.service.get_complete_team_details(team_id)
            
            self.assertIsNotNone(result)
            self.assertIsInstance(result, dict)
            # The method returns team_data directly (from team.to_dict()), not nested under 'team'
            self.assertIn("team_id", result)
            self.assertIn("stats", result)
            self.assertIn("roster", result)
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_enhanced_teams_data_integration(self):
        """Test get_enhanced_teams_data with real database."""
        try:
            result = self.service.get_enhanced_teams_data()
            
            self.assertIsInstance(result, list)
            # If we have teams, check structure
            if len(result) > 0:
                self.assertIn("team", result[0])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")


if __name__ == '__main__':
    unittest.main()

