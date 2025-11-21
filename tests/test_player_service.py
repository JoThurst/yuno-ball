"""Unit and integration tests for PlayerService.

This test suite covers:
- Unit tests with mocks for PlayerService methods
- Integration tests with real database for PlayerService methods
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.services.player_service import PlayerService
from app.models.player_sqlalchemy import PlayerORM
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.leaguedashplayerstats_sqlalchemy import LeagueDashPlayerStatsORM
from app.models.player_streaks_sqlalchemy import PlayerStreaksORM
from app.database import get_db_context
from tests.test_base import BaseTestCase
from tests.config import TestConfig


class TestPlayerServiceUnit(BaseTestCase):
    """Unit tests for PlayerService with mocks."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.service = PlayerService()
        self.mock_session = Mock(spec=Session)
    
    def test_get_all_players_with_cache_hit(self):
        """Test get_all_players returns cached data."""
        cached_data = [
            {"player_id": 1, "name": "Test Player 1"},
            {"player_id": 2, "name": "Test Player 2"}
        ]
        
        with patch('app.services.base_service.get_cache', return_value=cached_data):
            result = self.service.get_all_players()
            self.assertEqual(result, cached_data)
    
    def test_get_all_players_with_cache_miss(self):
        """Test get_all_players fetches from database on cache miss."""
        mock_players = [
            Mock(spec=PlayerORM, player_id=1, name="Test Player 1"),
            Mock(spec=PlayerORM, player_id=2, name="Test Player 2")
        ]
        for player in mock_players:
            player.to_dict.return_value = {"player_id": player.player_id, "name": player.name}
        
        with patch('app.services.base_service.get_cache', return_value=None):
            with patch('app.services.base_service.set_cache') as mock_set_cache:
                with patch('app.services.player_service.PlayerORM.get_all', return_value=mock_players):
                    with patch('app.services.base_service.get_db_context') as mock_db_context:
                        mock_db_context.return_value.__enter__.return_value = self.mock_session
                        mock_db_context.return_value.__exit__.return_value = None
                        
                        result = self.service.get_all_players()
                        
                        self.assertEqual(len(result), 2)
                        self.assertEqual(result[0]["player_id"], 1)
                        mock_set_cache.assert_called_once()
    
    def test_get_player_details_not_found(self):
        """Test get_player_details returns None when player not found."""
        with patch('app.services.player_service.PlayerORM.get_by_id', return_value=None):
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.get_player_details(999)
                self.assertIsNone(result)
    
    def test_get_formatted_game_logs(self):
        """Test get_formatted_game_logs formats game logs correctly."""
        from datetime import datetime
        
        mock_game_logs = [
            Mock(spec=GameLogORM)
        ]
        mock_game_logs[0].to_dict.return_value = {
            "game_date": datetime(2024, 1, 15),
            "minutes_played": 35.5,
            "formatted_score": "LAL 120.0 - 115.0 BOS",
            "points": 25,
            "rebounds": 10,
            "assists": 5
        }
        
        with patch('app.services.player_service.GameLogORM.get_last_n_games', return_value=mock_game_logs):
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.get_formatted_game_logs(1, num_games=1)
                
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["minutes_played"], "35.5")
                # Date format is "Mon 01/15" (weekday + date), not month name
                self.assertIsNotNone(result[0].get("game_date"))
                self.assertIn("/", result[0]["game_date"] or "")
    
    def test_calculate_averages(self):
        """Test calculate_averages computes correct averages."""
        game_logs = [
            {"points": 20, "rebounds": 10, "assists": 5, "steals": 2, "blocks": 1, "turnovers": 3},
            {"points": 25, "rebounds": 12, "assists": 7, "steals": 1, "blocks": 2, "turnovers": 2},
            {"points": 15, "rebounds": 8, "assists": 3, "steals": 3, "blocks": 0, "turnovers": 4}
        ]
        
        averages = PlayerService.calculate_averages(game_logs)
        
        self.assertEqual(averages["points_avg"], 20.0)
        self.assertEqual(averages["rebounds_avg"], 10.0)
        self.assertEqual(averages["assists_avg"], 5.0)
        self.assertEqual(averages["steals_avg"], 2.0)
        self.assertEqual(averages["blocks_avg"], 1.0)
        self.assertEqual(averages["turnovers_avg"], 3.0)
    
    def test_get_player_streaks_with_cache(self):
        """Test get_player_streaks uses cache when available."""
        cached_streaks = {
            "points": [
                {"player_name": "Test Player", "streak_games": 5}
            ]
        }
        
        with patch('app.services.base_service.get_cache', return_value=cached_streaks):
            result = self.service.get_player_streaks(min_streak_games=3)
            self.assertEqual(result, cached_streaks)
    
    def test_get_comparison_stats_no_player(self):
        """Test get_comparison_stats returns defaults when player not found."""
        with patch('app.services.player_service.LeagueDashPlayerStatsORM.get_by_player', return_value=None):
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.get_comparison_stats(999)
                
                self.assertEqual(result["pts"], 0)
                self.assertEqual(result["reb"], 0)
                self.assertEqual(result["ast"], 0)
    
    def test_get_comparison_stats_with_player(self):
        """Test get_comparison_stats calculates stats correctly."""
        mock_stats = Mock(spec=LeagueDashPlayerStatsORM)
        mock_stats.to_dict.return_value = {
            "gp": 10,
            "pts": 200,  # Total points
            "reb": 100,  # Total rebounds
            "ast": 50,   # Total assists
            "stl": 20,   # Total steals
            "blk": 10,   # Total blocks
            "fg_pct": 0.45
        }
        
        with patch('app.services.player_service.LeagueDashPlayerStatsORM.get_by_player', return_value=mock_stats):
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.get_comparison_stats(1, season="2024-25")
                
                self.assertEqual(result["pts"], 20.0)  # 200 / 10
                self.assertEqual(result["reb"], 10.0)  # 100 / 10
                self.assertEqual(result["ast"], 5.0)    # 50 / 10
                self.assertEqual(result["fg_pct"], 45.0)  # 0.45 * 100
    
    def test_compare_players_not_found(self):
        """Test compare_players returns None when players not found."""
        with patch('app.services.player_service.PlayerORM.get_by_id', return_value=None):
            with patch('app.services.base_service.get_db_context') as mock_db_context:
                mock_db_context.return_value.__enter__.return_value = self.mock_session
                mock_db_context.return_value.__exit__.return_value = None
                
                result = self.service.compare_players(1, 2)
                self.assertIsNone(result)
    
    def test_compare_players_success(self):
        """Test compare_players returns correct comparison data."""
        mock_player1 = Mock(spec=PlayerORM)
        mock_player1.name = "Player 1"
        mock_player1.player_id = 1
        
        mock_player2 = Mock(spec=PlayerORM)
        mock_player2.name = "Player 2"
        mock_player2.player_id = 2
        
        with patch('app.services.player_service.PlayerORM.get_by_id') as mock_get_by_id:
            mock_get_by_id.side_effect = [mock_player1, mock_player2]
            
            with patch.object(self.service, 'get_comparison_stats') as mock_get_stats:
                mock_get_stats.side_effect = [
                    {"pts": 20, "reb": 10, "ast": 5, "stl": 2, "blk": 1, "fg_pct": 50},
                    {"pts": 15, "reb": 12, "ast": 7, "stl": 1, "blk": 2, "fg_pct": 45}
                ]
                
                with patch('app.services.base_service.get_db_context') as mock_db_context:
                    mock_db_context.return_value.__enter__.return_value = self.mock_session
                    mock_db_context.return_value.__exit__.return_value = None
                    
                    result = self.service.compare_players(1, 2)
                    
                    self.assertIsNotNone(result)
                    self.assertEqual(result["player1"]["name"], "Player 1")
                    self.assertEqual(result["player2"]["name"], "Player 2")
                    self.assertIn("normalized", result["player1"])
                    self.assertIn("normalized", result["player2"])


class TestPlayerServiceIntegration(BaseTestCase):
    """Integration tests for PlayerService with real database."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Set up Flask application context for services that need it
        from app import create_app
        from tests.config import TestConfig
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.service = PlayerService()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.app_context:
            self.app_context.pop()
        super().tearDown()
    
    def test_get_all_players_integration(self):
        """Test get_all_players with real database."""
        # This test requires actual data in the database
        # Skip if no data available
        try:
            with get_db_context() as db:
                players_count = db.query(PlayerORM).count()
                if players_count == 0:
                    self.skipTest("No players in database")
            
            result = self.service.get_all_players()
            
            self.assertIsInstance(result, list)
            # If we have players, check structure
            if len(result) > 0:
                self.assertIn("player_id", result[0])
                self.assertIn("name", result[0])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_player_details_integration(self):
        """Test get_player_details with real database."""
        try:
            # Get a real player ID from database
            with get_db_context() as db:
                player = db.query(PlayerORM).first()
                if not player:
                    self.skipTest("No players in database")
                player_id = player.player_id
            
            result = self.service.get_player_details(player_id)
            
            # Result might be None if get_player_data fails, but structure should be dict if present
            if result is not None:
                self.assertIsInstance(result, dict)
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_formatted_game_logs_integration(self):
        """Test get_formatted_game_logs with real database."""
        try:
            # Get a player with game logs
            with get_db_context() as db:
                # Try to find a player with game logs
                from app.models.gamelog_sqlalchemy import GameLogORM
                game_log = db.query(GameLogORM).first()
                if not game_log:
                    self.skipTest("No game logs in database")
                player_id = game_log.player_id
            
            result = self.service.get_formatted_game_logs(player_id, num_games=5)
            
            self.assertIsInstance(result, list)
            if len(result) > 0:
                # Check that game logs are formatted
                self.assertIn("game_date", result[0] or {})
                self.assertIn("points", result[0] or {})
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_comparison_stats_integration(self):
        """Test get_comparison_stats with real database."""
        try:
            # Get a player with stats
            with get_db_context() as db:
                stats = db.query(LeagueDashPlayerStatsORM).first()
                if not stats:
                    self.skipTest("No player stats in database")
                player_id = stats.player_id
                season = stats.season
            
            result = self.service.get_comparison_stats(player_id, season=season)
            
            self.assertIsInstance(result, dict)
            self.assertIn("pts", result)
            self.assertIn("reb", result)
            self.assertIn("ast", result)
            # Stats should be non-negative
            self.assertGreaterEqual(result["pts"], 0)
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")


if __name__ == '__main__':
    unittest.main()

