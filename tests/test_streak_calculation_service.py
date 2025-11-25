"""Unit tests for StreakCalculationService.

This test suite covers:
- Consecutive streak calculation logic
- Recent form (window) calculation logic
- Edge cases (missing games, season boundaries)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from typing import List

from app.services.streak_calculation_service import StreakCalculationService
from app.models.gamelog_sqlalchemy import GameLogORM
from app.models.gameschedule_sqlalchemy import GameScheduleORM
from app.models.player_sqlalchemy import PlayerORM


class TestStreakCalculationService(unittest.TestCase):
    """Unit tests for StreakCalculationService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.service = StreakCalculationService()
        self.mock_db = Mock()
    
    def create_mock_game_log(self, player_id: int, game_id: str, points: int, 
                            rebounds: int, assists: int, team_id: int = 1) -> Mock:
        """Create a mock game log object."""
        log = Mock(spec=GameLogORM)
        log.player_id = player_id
        log.game_id = game_id
        log.points = points
        log.rebounds = rebounds
        log.assists = assists
        log.steals = 0
        log.blocks = 0
        log.team_id = team_id
        log.season = "2024-25"
        return log
    
    def test_get_stat_value_points(self):
        """Test getting points stat value."""
        log = self.create_mock_game_log(1, "001", 25, 10, 5)
        result = self.service.get_stat_value(log, 'PTS')
        self.assertEqual(result, 25)
    
    def test_get_stat_value_rebounds(self):
        """Test getting rebounds stat value."""
        log = self.create_mock_game_log(1, "001", 25, 10, 5)
        result = self.service.get_stat_value(log, 'REB')
        self.assertEqual(result, 10)
    
    def test_get_stat_value_pra(self):
        """Test calculating PRA (Points + Rebounds + Assists)."""
        log = self.create_mock_game_log(1, "001", 25, 10, 5)
        result = self.service.get_stat_value(log, 'PRA')
        self.assertEqual(result, 40)  # 25 + 10 + 5
    
    def test_get_stat_value_none(self):
        """Test getting stat value when stat is None."""
        log = self.create_mock_game_log(1, "001", 25, 10, 5)
        log.points = None
        result = self.service.get_stat_value(log, 'PTS')
        self.assertEqual(result, 0)
    
    def test_calculate_consecutive_streak_simple(self):
        """Test calculating a simple consecutive streak."""
        # _calculate_single_consecutive_streak expects chronological order (oldest first)
        # because it's called after reversal in _calculate_consecutive_streaks_internal
        # Points: 20, 22, 18, 25, 24 (chronological)
        # Last 2 games (004, 005) = 25, 24 are the streak
        # Most recent game is at index 4 (005 with 24 points)
        game_logs = [
            self.create_mock_game_log(1, "001", 20, 5, 3),  # Oldest
            self.create_mock_game_log(1, "002", 22, 5, 3),
            self.create_mock_game_log(1, "003", 18, 5, 3),  # Below threshold
            self.create_mock_game_log(1, "004", 25, 5, 3),  # Streak starts
            self.create_mock_game_log(1, "005", 24, 5, 3),  # Most recent - in streak
        ]
        
        # Mock game dates
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                streak = self.service._calculate_single_consecutive_streak(
                    game_logs, 'PTS', 20, 1, "Test Player", "2024-25", self.mock_db
                )
        
        self.assertIsNotNone(streak)
        self.assertEqual(streak['streak_games'], 2)
        self.assertEqual(streak['threshold'], 20)
        self.assertTrue(streak['is_active'])  # Most recent game (index 4, 005) is in streak
        self.assertEqual(streak['streak_kind'], 'current')
    
    def test_calculate_consecutive_streak_broken(self):
        """Test calculating streak when it's broken."""
        # _calculate_single_consecutive_streak expects chronological order (oldest first)
        # Points: 25, 24, 18, 25, 24 (chronological)
        # Streak broken at 003, then new streak starts at 004, 005
        # Current active streak is last 2 games (004, 005)
        # Most recent game is at index 4 (005 with 24 points)
        game_logs = [
            self.create_mock_game_log(1, "001", 25, 5, 3),  # Oldest
            self.create_mock_game_log(1, "002", 24, 5, 3),
            self.create_mock_game_log(1, "003", 18, 5, 3),  # Below threshold - breaks streak
            self.create_mock_game_log(1, "004", 25, 5, 3),  # New streak starts
            self.create_mock_game_log(1, "005", 24, 5, 3),  # Most recent - in streak
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                streak = self.service._calculate_single_consecutive_streak(
                    game_logs, 'PTS', 20, 1, "Test Player", "2024-25", self.mock_db
                )
        
        self.assertIsNotNone(streak)
        self.assertEqual(streak['streak_games'], 2)  # Current active streak is 2 games (004, 005)
        self.assertTrue(streak['is_active'])  # Most recent game (index 4, 005) is in streak
    
    def test_calculate_consecutive_streak_no_streak(self):
        """Test when there's no active streak."""
        # _calculate_single_consecutive_streak expects chronological order (oldest first)
        # All below threshold
        game_logs = [
            self.create_mock_game_log(1, "001", 15, 5, 3),  # Oldest
            self.create_mock_game_log(1, "002", 18, 5, 3),
            self.create_mock_game_log(1, "003", 12, 5, 3),  # Most recent
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            streak = self.service._calculate_single_consecutive_streak(
                game_logs, 'PTS', 20, 1, "Test Player", "2024-25", self.mock_db
            )
        
        self.assertIsNone(streak)  # No streak
    
    def test_calculate_season_max_streak(self):
        """Test calculating season-best streak."""
        # _calculate_season_max_streak expects chronological order (oldest first)
        # Points: 25, 24, 18, 25, 24, 26, 23, 15, 25 (chronological)
        # Streak 1: 001-002 (2 games)
        # Streak 2: 004-007 (4 games) - longest
        # Streak 3: 009 (1 game)
        game_logs = [
            self.create_mock_game_log(1, "001", 25, 5, 3),  # Oldest - Streak 1 starts
            self.create_mock_game_log(1, "002", 24, 5, 3),  # Streak 1 continues
            self.create_mock_game_log(1, "003", 18, 5, 3),  # Break
            self.create_mock_game_log(1, "004", 25, 5, 3),  # Streak 2 starts
            self.create_mock_game_log(1, "005", 24, 5, 3),  # Streak 2 continues
            self.create_mock_game_log(1, "006", 26, 5, 3),  # Streak 2 continues
            self.create_mock_game_log(1, "007", 23, 5, 3),  # Streak 2 continues
            self.create_mock_game_log(1, "008", 15, 5, 3),  # Break
            self.create_mock_game_log(1, "009", 25, 5, 3),  # Most recent - Streak 3
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            streak = self.service._calculate_season_max_streak(
                game_logs, 'PTS', 20, 1, "Test Player", "2024-25", self.mock_db
            )
        
        self.assertIsNotNone(streak)
        self.assertEqual(streak['streak_games'], 4)  # Longest streak
        self.assertFalse(streak['is_active'])  # Season max is never active
        self.assertEqual(streak['streak_kind'], 'season_max')
    
    def test_calculate_stat_window_5_games(self):
        """Test calculating recent form for 5-game window."""
        # Create game logs: 4 of 5 games with 20+ points
        # Note: game logs are ordered most recent first (desc)
        game_logs = [
            self.create_mock_game_log(1, "005", 24, 5, 3),  # Most recent - Hit
            self.create_mock_game_log(1, "004", 25, 5, 3),  # Hit
            self.create_mock_game_log(1, "003", 18, 5, 3),  # Miss
            self.create_mock_game_log(1, "002", 24, 5, 3),  # Hit
            self.create_mock_game_log(1, "001", 25, 5, 3),  # Oldest - Hit
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(GameLogORM, 'get_by_player_and_season', return_value=game_logs):
                with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                    windows = self.service.calculate_stat_windows(
                        1, "2024-25", window_sizes=[5], stats=['PTS'], 
                        thresholds={'PTS': [20]}, db=self.mock_db
                    )
        
        self.assertEqual(len(windows), 1)
        window = windows[0]
        self.assertEqual(window['window_size'], 5)
        self.assertEqual(window['games_played'], 5)
        self.assertEqual(window['games_hit'], 4)  # 4 of 5 games
        self.assertEqual(window['threshold'], 20)
    
    def test_calculate_stat_window_10_games(self):
        """Test calculating recent form for 10-game window."""
        # Create game logs: 8 of last 10 games with 20+ points
        game_logs = [
            self.create_mock_game_log(1, f"00{i}", 25 if i % 5 != 0 else 15, 5, 3)
            for i in range(1, 11)  # Games 5 and 10 are misses
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(GameLogORM, 'get_by_player_and_season', return_value=game_logs):
                with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                    windows = self.service.calculate_stat_windows(
                        1, "2024-25", [10], ['PTS'], {'PTS': [20]}, db=self.mock_db
                    )
        
        self.assertEqual(len(windows), 1)
        window = windows[0]
        self.assertEqual(window['window_size'], 10)
        self.assertEqual(window['games_played'], 10)
        self.assertEqual(window['games_hit'], 8)  # 8 of 10 games
    
    def test_calculate_stat_window_missing_games(self):
        """Test window calculation when player has fewer games than window size."""
        # Only 3 games, but window size is 5
        game_logs = [
            self.create_mock_game_log(1, "003", 23, 5, 3),  # Most recent
            self.create_mock_game_log(1, "002", 24, 5, 3),
            self.create_mock_game_log(1, "001", 25, 5, 3),  # Oldest
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(GameLogORM, 'get_by_player_and_season', return_value=game_logs):
                with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                    windows = self.service.calculate_stat_windows(
                        1, "2024-25", window_sizes=[5], stats=['PTS'], 
                        thresholds={'PTS': [20]}, db=self.mock_db
                    )
        
        self.assertEqual(len(windows), 1)
        window = windows[0]
        self.assertEqual(window['window_size'], 5)
        self.assertEqual(window['games_played'], 3)  # Only 3 games available
        self.assertEqual(window['games_hit'], 3)  # All 3 hit
    
    def test_get_game_date(self):
        """Test getting game date from schedule."""
        mock_schedule = Mock(spec=GameScheduleORM)
        mock_schedule.game_date = datetime(2024, 12, 1, 20, 0, 0)
        
        with patch.object(GameScheduleORM, 'get_by_game_and_team', return_value=mock_schedule):
            result = self.service.get_game_date("001", 1, self.mock_db)
        
        self.assertEqual(result, date(2024, 12, 1))
    
    def test_get_game_date_not_found(self):
        """Test getting game date when schedule not found."""
        with patch.object(GameScheduleORM, 'get_by_game_and_team', return_value=None):
            result = self.service.get_game_date("001", 1, self.mock_db)
        
        self.assertIsNone(result)
    
    def test_calculate_consecutive_streaks_no_logs(self):
        """Test calculating streaks when player has no game logs."""
        with patch.object(GameLogORM, 'get_by_player_and_season', return_value=[]):
            with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                streaks = self.service.calculate_consecutive_streaks(
                    1, "2024-25", db=self.mock_db
                )
        
        self.assertEqual(len(streaks), 0)
    
    def test_calculate_consecutive_streaks_multiple_stats(self):
        """Test calculating streaks for multiple stats."""
        # _calculate_consecutive_streaks_internal will reverse these, so pass in DESC order
        # But since we're testing the internal method directly, we need chronological order
        # Actually, wait - let me check what method we're calling...
        # We're calling calculate_consecutive_streaks which calls _calculate_consecutive_streaks_internal
        # which reverses the logs, so we should pass DESC order
        # But the test mocks GameLogORM.get_by_player_and_season which returns DESC order
        # So the test should work with DESC order
        game_logs = [
            self.create_mock_game_log(1, "003", 23, 12, 4),  # Most recent - All stats hit
            self.create_mock_game_log(1, "002", 24, 8, 6),  # All stats hit
            self.create_mock_game_log(1, "001", 25, 10, 5), # Oldest - All stats hit
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(GameLogORM, 'get_by_player_and_season', return_value=game_logs):
                with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                    streaks = self.service.calculate_consecutive_streaks(
                        1, "2024-25", stats=['PTS', 'REB'], 
                        thresholds={'PTS': [20], 'REB': [8]}, db=self.mock_db
                    )
        
        # Should have 4 streaks: current PTS, season_max PTS, current REB, season_max REB
        self.assertGreaterEqual(len(streaks), 4)
        
        # Check that we have both PTS and REB streaks
        stats_found = {s['stat'] for s in streaks}
        self.assertIn('PTS', stats_found)
        self.assertIn('REB', stats_found)
    
    def test_calculate_stat_windows_multiple_windows(self):
        """Test calculating windows for multiple window sizes."""
        game_logs = [
            self.create_mock_game_log(1, f"00{i}", 25, 5, 3)
            for i in range(1, 11)
        ]
        
        with patch.object(self.service, 'get_game_date', return_value=date.today()):
            with patch.object(GameLogORM, 'get_by_player_and_season', return_value=game_logs):
                with patch.object(PlayerORM, 'get_by_id', return_value=Mock(name="Test Player", player_id=1)):
                    windows = self.service.calculate_stat_windows(
                        1, "2024-25", window_sizes=[5, 10], 
                        stats=['PTS'], thresholds={'PTS': [20]}, db=self.mock_db
                    )
        
        # Should have 2 windows: 5-game and 10-game
        self.assertEqual(len(windows), 2)
        
        window_sizes = {w['window_size'] for w in windows}
        self.assertIn(5, window_sizes)
        self.assertIn(10, window_sizes)


if __name__ == '__main__':
    unittest.main()

