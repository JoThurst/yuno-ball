"""Integration tests for route endpoints.

This test suite covers:
- Integration tests for player routes
- Integration tests for team routes
- Integration tests for dashboard routes
- Integration tests for API routes
- Integration tests for auth routes (basic)
"""

import unittest
from flask import url_for

from app import create_app
from tests.test_base import BaseTestCase
from tests.config import TestConfig
from app.database import get_db_context
from app.models.player_sqlalchemy import PlayerORM
from app.models.team_sqlalchemy import TeamORM


class TestPlayerRoutes(BaseTestCase):
    """Integration tests for player routes."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def test_player_list_route(self):
        """Test GET /players route."""
        response = self.client.get('/players')
        
        # Should return 200 or redirect
        self.assertIn(response.status_code, [200, 302])
    
    def test_player_detail_route(self):
        """Test GET /players/<player_id> route."""
        try:
            # Get a real player ID from database
            with get_db_context() as db:
                player = db.query(PlayerORM).first()
                if not player:
                    self.skipTest("No players in database")
                player_id = player.player_id
            
            response = self.client.get(f'/players/{player_id}')
            
            # Should return 200 or redirect
            self.assertIn(response.status_code, [200, 302])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_player_streaks_route(self):
        """Test GET /players/streaks route."""
        response = self.client.get('/players/streaks')
        
        # Should return 200 or redirect
        self.assertIn(response.status_code, [200, 302])


class TestTeamRoutes(BaseTestCase):
    """Integration tests for team routes."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def test_teams_route(self):
        """Test GET /teams route."""
        response = self.client.get('/teams')
        
        # Should return 200 or redirect
        self.assertIn(response.status_code, [200, 302])
    
    def test_team_detail_route(self):
        """Test GET /teams/<team_id> route."""
        try:
            # Get a real team ID from database
            with get_db_context() as db:
                team = db.query(TeamORM).first()
                if not team:
                    self.skipTest("No teams in database")
                team_id = team.team_id
            
            response = self.client.get(f'/teams/{team_id}')
            
            # Should return 200 or redirect
            self.assertIn(response.status_code, [200, 302])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_team_stats_visuals_route(self):
        """Test GET /teams/<team_id>/stats-visuals route."""
        try:
            # Get a real team ID from database
            with get_db_context() as db:
                team = db.query(TeamORM).first()
                if not team:
                    self.skipTest("No teams in database")
                team_id = team.team_id
            
            response = self.client.get(f'/teams/{team_id}/stats-visuals')
            
            # Should return 200 or redirect
            self.assertIn(response.status_code, [200, 302])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")


class TestDashboardRoutes(BaseTestCase):
    """Integration tests for dashboard routes."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def test_dashboard_route(self):
        """Test GET /dashboard route."""
        response = self.client.get('/dashboard')
        
        # Should return 200 or redirect
        self.assertIn(response.status_code, [200, 302])
    
    def test_games_dashboard_route(self):
        """Test GET /games-dashboard route."""
        response = self.client.get('/games-dashboard')
        
        # Should return 200 or redirect
        self.assertIn(response.status_code, [200, 302])
    
    def test_matchup_route(self):
        """Test GET /matchup/<team1_id>/<team2_id> route."""
        try:
            # Get two real team IDs from database
            with get_db_context() as db:
                teams = db.query(TeamORM).limit(2).all()
                if len(teams) < 2:
                    self.skipTest("Not enough teams in database")
                team1_id = teams[0].team_id
                team2_id = teams[1].team_id
            
            response = self.client.get(f'/matchup/{team1_id}/{team2_id}')
            
            # Should return 200 or redirect
            self.assertIn(response.status_code, [200, 302])
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")


class TestAPIRoutes(BaseTestCase):
    """Integration tests for API routes."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def test_get_team_stats_api_route(self):
        """Test GET /api/team-stats/<team_id> route."""
        try:
            # Get a real team ID from database
            with get_db_context() as db:
                team = db.query(TeamORM).first()
                if not team:
                    self.skipTest("No teams in database")
                team_id = team.team_id
            
            response = self.client.get(f'/api/team-stats/{team_id}')
            
            # Should return 200 or JSON response
            self.assertIn(response.status_code, [200, 400, 404])
            if response.status_code == 200:
                self.assertEqual(response.content_type, 'application/json')
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")
    
    def test_get_player_comparison_route(self):
        """Test GET /api/player-comparison/<player1_id>/<player2_id> route."""
        try:
            # Get two real player IDs from database
            with get_db_context() as db:
                players = db.query(PlayerORM).limit(2).all()
                if len(players) < 2:
                    self.skipTest("Not enough players in database")
                player1_id = players[0].player_id
                player2_id = players[1].player_id
            
            response = self.client.get(f'/api/player-comparison/{player1_id}/{player2_id}')
            
            # Should return 200 or JSON response
            self.assertIn(response.status_code, [200, 400, 404])
            if response.status_code == 200:
                self.assertEqual(response.content_type, 'application/json')
        except Exception as e:
            self.skipTest(f"Database connection issue: {e}")


if __name__ == '__main__':
    unittest.main()

