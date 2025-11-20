"""SQLAlchemy User model with backward compatibility.

This module provides the SQLAlchemy ORM version of the User model.
It maintains full compatibility with the existing psycopg2-based User class.
"""
import bcrypt
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt
from flask import current_app
from flask_login import UserMixin
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Index
)
from sqlalchemy.orm import Session

from app.database import Base, get_db_context
from app.utils.rate_limiter import check_login_attempts, reset_login_attempts
from app.utils.cache_utils import set_cache, get_cache

logger = logging.getLogger(__name__)


class UserORM(Base, UserMixin):
    """
    SQLAlchemy ORM User model for authentication and user management.
    
    This is the modern SQLAlchemy version that will gradually replace
    the psycopg2-based User class.
    """
    __tablename__ = 'users'
    __table_args__ = (
        Index('idx_users_username', 'username'),
        Index('idx_users_email', 'email'),
        {'schema': 'public'}  # Explicitly set schema
    )
    
    # Columns
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    
    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}', email='{self.email}')>"
    
    # Flask-Login integration
    @property
    def id(self):
        """Required by Flask-Login - return the user_id."""
        return self.user_id
    
    def get_id(self):
        """Required by Flask-Login - return the user_id as string."""
        return str(self.user_id)
    
    # Authentication Methods
    
    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """
        Validate password complexity requirements.
        
        Requirements:
        - At least 8 characters long
        - Contains at least one uppercase letter
        - Contains at least one lowercase letter
        - Contains at least one number
        - Contains at least one special character
        
        Returns:
            tuple: (bool, str) - (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
            
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"
            
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"
            
        if not re.search(r"\d", password):
            return False, "Password must contain at least one number"
            
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must contain at least one special character"
            
        return True, "Password is valid"
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    # Query Methods
    
    @classmethod
    def get_by_id(cls, user_id: int, db: Optional[Session] = None) -> Optional['UserORM']:
        """Get user by user_id."""
        if db:
            return db.query(cls).filter(cls.user_id == user_id).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.user_id == user_id).first()
    
    @classmethod
    def get_by_username(cls, username: str, db: Optional[Session] = None) -> Optional['UserORM']:
        """Get user by username."""
        if db:
            return db.query(cls).filter(cls.username == username).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.username == username).first()
    
    @classmethod
    def get_by_email(cls, email: str, db: Optional[Session] = None) -> Optional['UserORM']:
        """Get user by email."""
        if db:
            return db.query(cls).filter(cls.email == email).first()
        
        with get_db_context() as db:
            return db.query(cls).filter(cls.email == email).first()
    
    # CRUD Operations
    
    @classmethod
    def create(cls, username: str, email: str, password: str, 
               is_admin: bool = False, db: Optional[Session] = None) -> 'UserORM':
        """
        Create a new user.
        
        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password to be hashed
            is_admin: Whether the user has admin privileges
            db: Optional database session
            
        Returns:
            UserORM: The created user instance
            
        Raises:
            ValueError: If password validation fails
        """
        # Validate password
        is_valid, error_message = cls.validate_password(password)
        if not is_valid:
            logger.error(f"Password validation failed: {error_message}")
            raise ValueError(error_message)
        
        # Hash password
        password_hash = cls.hash_password(password)
        
        # Create user
        user = cls(
            username=username,
            email=email,
            password_hash=password_hash,
            is_admin=is_admin,
            is_active=False  # Require email verification
        )
        
        if db:
            db.add(user)
            db.flush()  # Flush to get user_id without committing
            return user
        
        with get_db_context() as db:
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
    
    def update_password(self, new_password: str, db: Optional[Session] = None) -> None:
        """Update user's password."""
        self.password_hash = self.hash_password(new_password)
        
        if db:
            db.commit()
        else:
            with get_db_context() as db:
                db.merge(self)
                db.commit()
    
    def update_email(self, new_email: str, db: Optional[Session] = None) -> None:
        """Update user's email and deactivate account for re-verification."""
        self.email = new_email
        self.is_active = False
        
        if db:
            db.commit()
        else:
            with get_db_context() as db:
                db.merge(self)
                db.commit()
    
    def activate(self, db: Optional[Session] = None) -> None:
        """Activate user account."""
        self.is_active = True
        
        if db:
            db.commit()
        else:
            with get_db_context() as db:
                db.merge(self)
                db.commit()
    
    def deactivate(self, db: Optional[Session] = None) -> None:
        """Deactivate user account."""
        self.is_active = False
        
        if db:
            db.commit()
        else:
            with get_db_context() as db:
                db.merge(self)
                db.commit()
    
    def delete(self, db: Optional[Session] = None) -> None:
        """Delete user account."""
        if db:
            db.delete(self)
            db.commit()
        else:
            with get_db_context() as db:
                db.delete(self)
                db.commit()
    
    def update_last_login(self, db: Optional[Session] = None) -> None:
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        
        if db:
            db.commit()
        else:
            with get_db_context() as db:
                db.merge(self)
                db.commit()
    
    # Authentication
    
    @classmethod
    def authenticate(cls, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: Username to authenticate
            password: Password to verify
            
        Returns:
            dict: User information and JWT token if successful, None if failed
            
        Raises:
            ValueError: If too many login attempts
        """
        # Check login attempts
        if not check_login_attempts(username):
            raise ValueError("Too many login attempts. Please try again in 5 minutes.")
        
        with get_db_context() as db:
            # Get user by username
            user = db.query(cls).filter(
                cls.username == username,
                cls.is_active == True
            ).first()
            
            if not user:
                return None
            
            # Verify password
            if not user.check_password(password):
                return None
            
            # Reset login attempts on successful login
            reset_login_attempts(username)
            
            # Update last login
            user.update_last_login(db=db)
            
            # Generate JWT token
            token = jwt.encode(
                {
                    'user_id': user.user_id,
                    'username': user.username,
                    'is_admin': user.is_admin,
                    'exp': datetime.utcnow() + current_app.config['JWT_EXPIRATION_DELTA']
                },
                current_app.config['JWT_SECRET_KEY'],
                algorithm='HS256'
            )
            
            return {
                'user_id': user.user_id,
                'username': user.username,
                'email': user.email,
                'is_admin': user.is_admin,
                'token': token
            }
    
    # Password Reset
    
    def generate_reset_token(self, email: Optional[str] = None) -> str:
        """
        Generate a password reset token for the user.
        
        Args:
            email: The email address to verify. If provided, must match user's email.
            
        Returns:
            str: JWT reset token
            
        Raises:
            ValueError: If email doesn't match
        """
        try:
            # If email is provided, verify it matches the user's email
            if email and email != self.email:
                raise ValueError("Email does not match user's email")
            
            # Generate a JWT token with user_id and expiration time
            token = jwt.encode(
                {
                    'user_id': self.user_id,
                    'email': self.email,
                    'exp': datetime.utcnow() + timedelta(hours=1)
                },
                current_app.config['SECRET_KEY'],
                algorithm='HS256'
            )
            
            # Store the token in Redis with expiration
            set_cache(f"reset_token:{token}", str(self.user_id), ex=3600)  # 1 hour
            
            return token
        except Exception as e:
            logger.error(f"Error generating reset token: {str(e)}")
            raise
    
    @classmethod
    def verify_reset_token(cls, token: str) -> Optional['UserORM']:
        """
        Verify password reset token.
        
        Args:
            token: JWT reset token
            
        Returns:
            UserORM: User if token is valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            
            user = cls.get_by_id(payload['user_id'])
            if user and user.email == payload.get('email'):
                return user
            return None
        except Exception as e:
            logger.error(f"Error verifying reset token: {e}")
            return None
    
    # Utility Methods
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active,
            'is_admin': self.is_admin
        }


