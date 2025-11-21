"""Unit tests for route endpoints with mocks.

This test suite covers:
- Unit tests for player routes (mocking services)
- Unit tests for team routes (mocking services)
- Unit tests for dashboard routes (mocking services)
- Unit tests for API routes (mocking services and ORM)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from flask import url_for

from app import create_app
from tests.test_base import BaseTestCase
from tests.config import TestConfig


class TestPlayerRoutesUnit(BaseTestCase):
    """Unit tests for player routes with mocks."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
        super().tearDown()
    
    def test_player_list_route(self):
        """Test GET /players route with mocked service."""
        mock_players = [
            {"player_id": 1, "name": "Player 1", "team_abbreviation": "LAL"},
            {"player_id": 2, "name": "Player 2", "team_abbreviation": "BOS"}
        ]
        
        with patch('app.routes.player_routes.PlayerService.get_all_players', return_value=mock_players):
            response = self.client.get('/players')
            
            self.assertEqual(response.status_code, 200)
    
    def test_player_detail_route_success(self):
        """Test GET /players/<player_id> route with mocked service."""
        mock_player_data = {
            "player_id": 1,
            "name": "Test Player",
            "roster": {"team_id": 1}
        }
        mock_team_info = {"team_id": 1, "name": "Test Team", "abbreviation": "TT"}
        
        with patch('app.routes.player_routes.PlayerService.get_player_details', return_value=mock_player_data):
            with patch('app.routes.player_routes.TeamORM.get_by_id') as mock_get_team:
                mock_team_orm = Mock()
                mock_team_orm.to_dict.return_value = mock_team_info
                mock_get_team.return_value = mock_team_orm
                
                with patch('app.routes.player_routes.get_db_context') as mock_db:
                    mock_db.return_value.__enter__.return_value = Mock()
                    mock_db.return_value.__exit__.return_value = None
                    
                    response = self.client.get('/players/1')
                    
                    self.assertEqual(response.status_code, 200)
    
    def test_player_detail_route_not_found(self):
        """Test GET /players/<player_id> route when player not found."""
        with patch('app.routes.player_routes.PlayerService.get_player_details', return_value=None):
            response = self.client.get('/players/999')
            
            self.assertEqual(response.status_code, 404)
    
    def test_player_streaks_route(self):
        """Test GET /players/streaks route with mocked ORM."""
        from datetime import date
        mock_games = [
            {
                "game_id": "001",
                "team_id": 1,
                "opponent_team_id": 2,
                "home_or_away": "H"
            }
        ]
        
        with patch('app.routes.player_routes.GameScheduleORM.get_by_date', return_value=mock_games):
            with patch('app.routes.player_routes.PlayerStreaksORM.get_streaks_by_team', return_value=[]):
                with patch('app.routes.player_routes.get_db_context') as mock_db:
                    mock_db.return_value.__enter__.return_value = Mock()
                    mock_db.return_value.__exit__.return_value = None
                    
                    response = self.client.get('/players/streaks')
                    
                    self.assertEqual(response.status_code, 200)


class TestTeamRoutesUnit(BaseTestCase):
    """Unit tests for team routes with mocks."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
        super().tearDown()
    
    def test_teams_route(self):
        """Test GET /team/list route."""
        # Note: This route uses get_enhanced_teams_data which still uses old models
        # We'll mock it for now
        mock_teams = [
            {"team_id": 1, "name": "Team 1", "abbreviation": "T1"},
            {"team_id": 2, "name": "Team 2", "abbreviation": "T2"}
        ]
        
        with patch('app.routes.team_routes.get_enhanced_teams_data', return_value=mock_teams):
            response = self.client.get('/team/list')
            
            self.assertEqual(response.status_code, 200)
    
    def test_team_detail_route_success(self):
        """Test GET /team/<team_id> route with mocked service."""
        mock_team_data = {
            "team_id": 1,
            "name": "Test Team",
            "abbreviation": "TT",
            "stats": {"pts": 100, "reb": 50}
        }
        
        with patch('app.routes.team_routes.TeamService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_complete_team_details.return_value = mock_team_data
            mock_service_class.return_value = mock_service
            
            response = self.client.get('/team/1')
            
            self.assertEqual(response.status_code, 200)
            mock_service.get_complete_team_details.assert_called_once_with(1)
    
    def test_team_detail_route_not_found(self):
        """Test GET /team/<team_id> route when team not found."""
        with patch('app.routes.team_routes.TeamService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_complete_team_details.return_value = None
            mock_service_class.return_value = mock_service
            
            response = self.client.get('/team/999')
            
            self.assertEqual(response.status_code, 404)
    
    def test_team_stats_visuals_route(self):
        """Test GET /team/stats-visuals route with mocked service."""
        mock_data = {
            "team_names": ["Team 1", "Team 2"],
            "team_ppg": [100, 95],
            "team_rpg": [50, 45],
            "team_apg": [25, 22],
            "team_fg_pct": [0.45, 0.42]
        }
        
        with patch('app.routes.team_routes.TeamService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_team_visuals_data.return_value = mock_data
            mock_service_class.return_value = mock_service
            
            response = self.client.get('/team/stats-visuals')
            
            self.assertEqual(response.status_code, 200)


class TestDashboardRoutesUnit(BaseTestCase):
    """Unit tests for dashboard routes with mocks."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
        super().tearDown()
    
    def test_dashboard_route(self):
        """Test GET /dashboard route with mocked ORM."""
        mock_player_stats = [
            {"player_id": 1, "pts": 25.0, "reb": 10.0}
        ]
        mock_teams = [
            {"team_id": 1, "name": "Team 1", "abbreviation": "T1"}
        ]
        
        with patch('app.routes.dashboard_routes.LeagueDashPlayerStatsORM.get_all_by_season', return_value=[]):
            with patch('app.routes.dashboard_routes.TeamORM.get_all', return_value=[]):
                with patch('app.routes.dashboard_routes.get_db_context') as mock_db:
                    mock_session = Mock()
                    # Mock the query results
                    mock_query = Mock()
                    mock_query.all.return_value = []
                    mock_session.query.return_value = mock_query
                    
                    mock_db.return_value.__enter__.return_value = mock_session
                    mock_db.return_value.__exit__.return_value = None
                    
                    response = self.client.get('/dashboard')
                    
                    self.assertEqual(response.status_code, 200)
    
    def test_games_dashboard_route(self):
        """Test GET /games-dashboard route."""
        # This route uses DashboardService.get_home_dashboard_data
        mock_dashboard_data = {
            "featured_games": [],
            "games": [],
            "standings": {"East": [], "West": []}
        }
        
        with patch('app.routes.dashboard_routes.get_home_dashboard_data', return_value=mock_dashboard_data):
            response = self.client.get('/games-dashboard')
            
            self.assertEqual(response.status_code, 200)
    
    def test_matchup_route(self):
        """Test GET /matchup/<team1_id>/<team2_id> route."""
        # This route uses DashboardService methods
        mock_matchup_data = {
            "team1": {"name": "Team 1"},
            "team2": {"name": "Team 2"},
            "games": []
        }
        
        with patch('app.routes.dashboard_routes.DashboardService.get_matchup_data', return_value=mock_matchup_data):
            response = self.client.get('/matchup/1/2')
            
            self.assertIn(response.status_code, [200, 302])


class TestAPIRoutesUnit(BaseTestCase):
    """Unit tests for API routes with mocks."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
        super().tearDown()
    
    def test_get_team_stats_api_success(self):
        """Test GET /api/team-stats?team_id=1 route with mocked services and ORM."""
        mock_team_data = {
            "team_id": 1,
            "name": "Test Team",
            "abbreviation": "TT",
            "record": "50-32"
        }
        mock_rankings = [
            {"team_id": 1, "pts_rank": 5, "reb_rank": 10, "ast_rank": 8, "fgm_rank": 12}
        ]
        mock_games = [
            Mock(to_dict=lambda: {
                "game_id": "001",
                "home_team_id": 1,
                "away_team_id": 2,
                "game_date": "2024-01-15",
                "score": "120-115",
                "result": "W"
            })
        ]
        mock_opponent = Mock()
        mock_opponent.abbreviation = "OPP"
        
        with patch('app.routes.api_routes.TeamService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_complete_team_details.return_value = mock_team_data
            mock_service_class.return_value = mock_service
            
            with patch('app.routes.api_routes.LeagueDashTeamStatsORM.get_team_rankings', return_value=mock_rankings):
                with patch('app.routes.api_routes.GameScheduleORM.get_last_n_games', return_value=mock_games):
                    with patch('app.routes.api_routes.TeamORM.get_by_id', return_value=mock_opponent):
                        with patch('app.routes.api_routes.get_db_context') as mock_db:
                            mock_session = Mock()
                            mock_db.return_value.__enter__.return_value = mock_session
                            mock_db.return_value.__exit__.return_value = None
                            
                            response = self.client.get('/api/team-stats?team_id=1')
                            
                            self.assertEqual(response.status_code, 200)
                            self.assertEqual(response.content_type, 'application/json')
                            data = response.get_json()
                            self.assertIn('name', data)
                            self.assertIn('stats', data)
                            self.assertIn('games', data)
    
    def test_get_team_stats_api_missing_team_id(self):
        """Test GET /api/team-stats route without team_id parameter."""
        response = self.client.get('/api/team-stats')
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)
    
    def test_get_team_stats_api_team_not_found(self):
        """Test GET /api/team-stats?team_id=999 route when team not found."""
        with patch('app.routes.api_routes.TeamService') as mock_service_class:
            mock_service = Mock()
            mock_service.get_complete_team_details.return_value = None
            mock_service_class.return_value = mock_service
            
            with patch('app.routes.api_routes.get_db_context') as mock_db:
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session
                mock_db.return_value.__exit__.return_value = None
                
                response = self.client.get('/api/team-stats?team_id=999')
                
                self.assertEqual(response.status_code, 404)
                data = response.get_json()
                self.assertIn('error', data)
    
    def test_get_player_comparison_api_success(self):
        """Test GET /api/player-comparison?player1_id=1&player2_id=2 route."""
        mock_comparison = {
            "player1": {"name": "Player 1", "pts": 25.0},
            "player2": {"name": "Player 2", "pts": 20.0}
        }
        
        with patch('app.routes.api_routes.PlayerService') as mock_service_class:
            mock_service = Mock()
            mock_service.compare_players.return_value = mock_comparison
            mock_service_class.return_value = mock_service
            
            response = self.client.get('/api/player-comparison?player1_id=1&player2_id=2')
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content_type, 'application/json')
            data = response.get_json()
            self.assertIn('player1', data)
            self.assertIn('player2', data)
    
    def test_get_player_comparison_api_missing_params(self):
        """Test GET /api/player-comparison route without required parameters."""
        response = self.client.get('/api/player-comparison?player1_id=1')
        
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn('error', data)
    
    def test_get_player_comparison_api_not_found(self):
        """Test GET /api/player-comparison route when players not found."""
        with patch('app.routes.api_routes.PlayerService') as mock_service_class:
            mock_service = Mock()
            mock_service.compare_players.return_value = None
            mock_service_class.return_value = mock_service
            
            response = self.client.get('/api/player-comparison?player1_id=1&player2_id=2')
            
            self.assertEqual(response.status_code, 404)
            data = response.get_json()
            self.assertIn('error', data)


if __name__ == '__main__':
    unittest.main()

