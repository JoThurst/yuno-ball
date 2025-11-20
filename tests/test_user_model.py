"""Tests for User model (both psycopg2 and SQLAlchemy versions).

This test suite verifies that both the legacy psycopg2 User model
and the new SQLAlchemy UserORM model work correctly and provide
the same functionality.
"""
import pytest
import bcrypt
from datetime import datetime
from unittest.mock import patch, MagicMock

# Try both user model approaches
try:
    from app.models.user_sqlalchemy import UserORM
    from app.database import get_db_context, Base, engine
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    UserORM = None

from app.models.user import User, get_user_model, create_user_adapter, _USE_SQLALCHEMY


class TestPasswordValidation:
    """Test password validation logic (same for both models)."""
    
    def test_password_too_short(self):
        """Test that short passwords are rejected."""
        is_valid, message = User.validate_password("Short1!")
        assert not is_valid
        assert "at least 8 characters" in message
    
    def test_password_no_uppercase(self):
        """Test that passwords without uppercase are rejected."""
        is_valid, message = User.validate_password("password123!")
        assert not is_valid
        assert "uppercase letter" in message
    
    def test_password_no_lowercase(self):
        """Test that passwords without lowercase are rejected."""
        is_valid, message = User.validate_password("PASSWORD123!")
        assert not is_valid
        assert "lowercase letter" in message
    
    def test_password_no_number(self):
        """Test that passwords without numbers are rejected."""
        is_valid, message = User.validate_password("Password!")
        assert not is_valid
        assert "number" in message
    
    def test_password_no_special(self):
        """Test that passwords without special characters are rejected."""
        is_valid, message = User.validate_password("Password123")
        assert not is_valid
        assert "special character" in message
    
    def test_valid_password(self):
        """Test that valid passwords are accepted."""
        is_valid, message = User.validate_password("SecurePass123!")
        assert is_valid
        assert message == "Password is valid"


@pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not available")
class TestUserORM:
    """Test SQLAlchemy UserORM model."""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """Setup test database before each test."""
        # Create tables
        Base.metadata.create_all(bind=engine)
        yield
        # Cleanup after test
        with get_db_context() as db:
            db.query(UserORM).delete()
            db.commit()
    
    def test_create_user(self):
        """Test creating a user with SQLAlchemy."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        assert user.user_id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active == False
        assert user.is_admin == False
        assert user.password_hash is not None
    
    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        password = "SecurePass123!"
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password=password
        )
        
        # Password hash should not equal plain password
        assert user.password_hash != password
        
        # Should be able to verify password
        assert user.check_password(password)
        assert not user.check_password("WrongPassword")
    
    def test_get_by_username(self):
        """Test retrieving user by username."""
        # Create user
        UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Retrieve user
        user = UserORM.get_by_username("testuser")
        assert user is not None
        assert user.username == "testuser"
        
        # Non-existent user
        user = UserORM.get_by_username("nonexistent")
        assert user is None
    
    def test_get_by_email(self):
        """Test retrieving user by email."""
        # Create user
        UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Retrieve user
        user = UserORM.get_by_email("test@example.com")
        assert user is not None
        assert user.email == "test@example.com"
        
        # Non-existent user
        user = UserORM.get_by_email("nonexistent@example.com")
        assert user is None
    
    def test_get_by_id(self):
        """Test retrieving user by ID."""
        # Create user
        created_user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Retrieve user
        user = UserORM.get_by_id(created_user.user_id)
        assert user is not None
        assert user.user_id == created_user.user_id
        
        # Non-existent ID
        user = UserORM.get_by_id(99999)
        assert user is None
    
    def test_update_password(self):
        """Test updating user password."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        old_hash = user.password_hash
        new_password = "NewSecure456!"
        
        user.update_password(new_password)
        
        # Password hash should change
        assert user.password_hash != old_hash
        
        # Should verify with new password
        assert user.check_password(new_password)
        assert not user.check_password("SecurePass123!")
    
    def test_update_email(self):
        """Test updating user email."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Activate user first
        user.activate()
        assert user.is_active == True
        
        # Update email should deactivate
        user.update_email("newemail@example.com")
        
        assert user.email == "newemail@example.com"
        assert user.is_active == False
    
    def test_activate_deactivate(self):
        """Test activating and deactivating user."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # User starts inactive
        assert user.is_active == False
        
        # Activate
        user.activate()
        assert user.is_active == True
        
        # Deactivate
        user.deactivate()
        assert user.is_active == False
    
    def test_delete_user(self):
        """Test deleting user."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        user_id = user.user_id
        user.delete()
        
        # User should not exist
        deleted_user = UserORM.get_by_id(user_id)
        assert deleted_user is None
    
    def test_flask_login_integration(self):
        """Test Flask-Login required properties."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Test required properties
        assert user.id == user.user_id
        assert user.get_id() == str(user.user_id)
        assert hasattr(user, 'is_active')
        assert hasattr(user, 'is_authenticated')
    
    def test_to_dict(self):
        """Test converting user to dictionary."""
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        user_dict = user.to_dict()
        
        assert user_dict['user_id'] == user.user_id
        assert user_dict['username'] == "testuser"
        assert user_dict['email'] == "test@example.com"
        assert 'password_hash' not in user_dict  # Should not expose password
        assert user_dict['is_active'] == False
        assert user_dict['is_admin'] == False
    
    @patch('app.models.user_sqlalchemy.check_login_attempts')
    @patch('app.models.user_sqlalchemy.reset_login_attempts')
    @patch('flask.current_app')
    def test_authenticate_success(self, mock_app, mock_reset, mock_check):
        """Test successful authentication."""
        # Setup mocks
        mock_check.return_value = True
        mock_app.config = {
            'JWT_SECRET_KEY': 'test_secret',
            'JWT_EXPIRATION_DELTA': datetime.timedelta(days=1)
        }
        
        # Create and activate user
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        user.activate()
        
        # Authenticate
        result = UserORM.authenticate("testuser", "SecurePass123!")
        
        assert result is not None
        assert result['username'] == "testuser"
        assert result['user_id'] == user.user_id
        assert 'token' in result
        
        # Should reset login attempts
        mock_reset.assert_called_once_with("testuser")
    
    @patch('app.models.user_sqlalchemy.check_login_attempts')
    def test_authenticate_wrong_password(self, mock_check):
        """Test authentication with wrong password."""
        mock_check.return_value = True
        
        # Create and activate user
        user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        user.activate()
        
        # Authenticate with wrong password
        result = UserORM.authenticate("testuser", "WrongPassword!")
        
        assert result is None
    
    @patch('app.models.user_sqlalchemy.check_login_attempts')
    def test_authenticate_inactive_user(self, mock_check):
        """Test authentication with inactive user."""
        mock_check.return_value = True
        
        # Create inactive user
        UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Should fail because user is inactive
        result = UserORM.authenticate("testuser", "SecurePass123!")
        
        assert result is None


class TestBackwardCompatibility:
    """Test backward compatibility between old and new User models."""
    
    def test_get_user_model(self):
        """Test that get_user_model returns the correct model."""
        UserModel = get_user_model()
        
        if _USE_SQLALCHEMY and UserORM is not None:
            assert UserModel == UserORM
        else:
            assert UserModel == User
    
    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not available")
    def test_create_user_adapter(self):
        """Test converting UserORM to legacy User."""
        # Create UserORM
        orm_user = UserORM.create(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )
        
        # Convert to User
        user = create_user_adapter(orm_user)
        
        assert isinstance(user, User)
        assert user.user_id == orm_user.user_id
        assert user.username == orm_user.username
        assert user.email == orm_user.email
        assert user.is_active == orm_user.is_active
        assert user.is_admin == orm_user.is_admin
    
    def test_create_user_adapter_none(self):
        """Test that adapter handles None gracefully."""
        user = create_user_adapter(None)
        assert user is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


