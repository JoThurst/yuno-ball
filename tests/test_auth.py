import unittest
from flask import url_for
from app import create_app
from app.models.user import User
from tests.config import TestConfig
from tests.test_base import BaseTestCase
from flask_wtf.csrf import generate_csrf
from app.config import get_connection, release_connection
import json

class TestAuth(BaseTestCase):
    def setUp(self):
        """Set up test client and test database."""
        self.app = create_app(TestConfig)
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Create test user
        self.test_user = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'Test123!@#'
        }
        
        # Create tables
        User.create_table()
    
    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()
    
    def register_user(self, username=None, email=None, password=None, confirm_password=None, activate=True):
        """Helper function to register a user."""
        response = self.client.post('/register', data={
            'username': username or self.test_user['username'],
            'email': email or self.test_user['email'],
            'password': password or self.test_user['password'],
            'confirm_password': confirm_password or self.test_user['password']
        }, follow_redirects=True)
        
        # After registration, set the user as active for testing if requested
        if response.status_code == 200 and activate:
            user = User.get_by_username(username or self.test_user['username'])
            if user:
                conn = get_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        UPDATE users SET is_active = TRUE WHERE user_id = %s;
                    """, (user.id,))
                    conn.commit()
                finally:
                    cur.close()
                    release_connection(conn)
        
        return response
    
    def login_user(self, username=None, password=None, remember=False):
        """Helper function to login a user."""
        return self.client.post('/login', data={
            'username': username or self.test_user['username'],
            'password': password or self.test_user['password'],
            'remember': remember
        }, follow_redirects=True)
    
    def test_register_success(self):
        """Test successful user registration."""
        response = self.register_user(activate=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Registration successful!', response.data)
        
        # Verify user exists in database
        user = User.get_by_username(self.test_user['username'])
        self.assertIsNotNone(user)
        self.assertEqual(user.email, self.test_user['email'])
        self.assertFalse(user.is_active)  # User should not be verified yet
    
    def test_register_duplicate_username(self):
        """Test registration with existing username."""
        # First registration
        self.register_user()
        
        # Try to register same username again
        response = self.register_user()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Username already exists', response.data)
    
    def test_register_duplicate_email(self):
        """Test registration with existing email."""
        # First registration
        self.register_user()
        
        # Try to register with same email
        response = self.register_user(username='newuser')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Email already registered', response.data)
    
    def test_register_invalid_password(self):
        """Test registration with invalid password."""
        # Test too short password
        response = self.register_user(password='short', confirm_password='short')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password does not meet complexity requirements', response.data)
        
        # Test password without uppercase
        response = self.register_user(password='test123!@#', confirm_password='test123!@#')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password does not meet complexity requirements', response.data)
        
        # Test password without special character
        response = self.register_user(password='Test123abc', confirm_password='Test123abc')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password does not meet complexity requirements', response.data)
    
    def test_login_success(self):
        """Test successful login."""
        self.register_user()
        response = self.login_user()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Logged in successfully', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        self.register_user()
        
        # Test wrong password
        response = self.login_user(password='wrongpass')
        self.assertIn(b'Invalid username or password', response.data)
        
        # Test non-existent user
        response = self.login_user(username='nonexistent')
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_logout(self):
        """Test user logout."""
        self.register_user()
        self.login_user()
        
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'You have been logged out', response.data)
    
    def test_password_reset_request(self):
        """Test password reset request."""
        self.register_user()
        
        response = self.client.post('/forgot-password', data={
            'email': self.test_user['email']
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password reset instructions have been sent', response.data)
    
    def test_change_password(self):
        """Test password change in settings."""
        self.register_user()
        self.login_user()
        
        response = self.client.post('/settings/change-password', data={
            'current_password': self.test_user['password'],
            'new_password': 'NewTest123!@#',
            'confirm_new_password': 'NewTest123!@#'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Password updated successfully', response.data)
        
        # Verify can login with new password
        response = self.login_user(password='NewTest123!@#')
        self.assertIn(b'Logged in successfully', response.data)
    
    def test_update_email(self):
        """Test email update in settings."""
        self.register_user()
        self.login_user()
        
        new_email = 'newemail@example.com'
        response = self.client.post('/settings/update-profile', data={
            'email': new_email
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Email updated', response.data)
        
        # Verify email was updated
        user = User.get_by_username(self.test_user['username'])
        self.assertEqual(user.email, new_email)
        self.assertFalse(user.is_active)  # Should require verification
    
    def test_delete_account(self):
        """Test account deletion."""
        self.register_user()
        self.login_user()
        
        response = self.client.post('/settings/delete-account', data={
            'password': self.test_user['password']
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your account has been deleted successfully', response.data)
        
        # Verify user no longer exists
        user = User.get_by_username(self.test_user['username'])
        self.assertIsNone(user)

if __name__ == '__main__':
    unittest.main() 