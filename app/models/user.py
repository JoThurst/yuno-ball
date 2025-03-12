from app.config import get_connection, release_connection
import bcrypt
import logging
from datetime import datetime, timedelta
import jwt
from flask import current_app
import re
from app.utils.rate_limiter import check_login_attempts, reset_login_attempts
from app.utils.cache_utils import set_cache, get_cache
from app.utils.email_utils import send_password_reset_email
from flask_login import UserMixin

class User(UserMixin):
    """
    User model for authentication and user management.
    Handles user creation, authentication, and token management.
    """
    
    def __init__(self, user_id, username, email, password_hash, is_active=False, is_admin=False):
        self.id = user_id  # This is required by Flask-Login
        self.user_id = user_id  # Add this for compatibility
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self._is_active = is_active  # Use private attribute
        self.is_admin = is_admin

    @property
    def is_active(self):
        """Return whether the user account is active."""
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        """Set the active status of the user account."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE users
                SET is_active = %s
                WHERE user_id = %s;
            """, (value, self.id))
            conn.commit()
            self._is_active = value
        except Exception as e:
            conn.rollback()
            logging.error(f"Error updating is_active: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_by_id(cls, user_id):
        """Get user by ID."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT user_id, username, email, password_hash, is_active, is_admin
                FROM users
                WHERE user_id = %s;
            """, (user_id,))
            
            result = cur.fetchone()
            if result:
                return cls(*result)
            return None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_by_username(cls, username):
        """Get user by username."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT user_id, username, email, password_hash, is_active, is_admin
                FROM users
                WHERE username = %s;
            """, (username,))
            
            result = cur.fetchone()
            if result:
                return cls(*result)
            return None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_by_email(cls, email):
        """Get user by email."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT user_id, username, email, password_hash, is_active, is_admin
                FROM users
                WHERE email = %s;
            """, (email,))
            
            result = cur.fetchone()
            if result:
                return cls(*result)
            return None
        finally:
            cur.close()
            release_connection(conn)

    @staticmethod
    def validate_password(password):
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

    @classmethod
    def create(cls, username, email, password_hash):
        """Create a new user."""
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            # Insert the new user with is_active=False
            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, is_active)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id
                """,
                (username, email, password_hash, False)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            
            # Return a new User instance with is_active=False
            return cls(user_id, username, email, password_hash, is_active=False)
        except Exception as e:
            current_app.logger.error(f"Error creating user: {str(e)}")
            raise
        finally:
            if cur:
                cur.close()
            if conn:
                release_connection(conn)

    def update_password(self, new_password_hash):
        """Update user's password."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE users
                SET password_hash = %s
                WHERE user_id = %s;
            """, (new_password_hash, self.id))
            conn.commit()
            self.password_hash = new_password_hash
        except Exception as e:
            conn.rollback()
            logging.error(f"Error updating password: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)

    def update_email(self, new_email):
        """Update user's email."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE users
                SET email = %s, is_active = FALSE
                WHERE user_id = %s;
            """, (new_email, self.id))
            conn.commit()
            self.email = new_email
            self._is_active = False
        except Exception as e:
            conn.rollback()
            logging.error(f"Error updating email: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)

    def delete(self):
        """Delete user account."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                DELETE FROM users
                WHERE user_id = %s;
            """, (self.id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Error deleting user: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn)

    def generate_reset_token(self, email=None):
        """
        Generate a password reset token for the user.
        
        Args:
            email (str, optional): The email address to verify. If provided,
                                 it must match the user's email.
        """
        try:
            # If email is provided, verify it matches the user's email
            if email and email != self.email:
                raise ValueError("Email does not match user's email")

            # Generate a JWT token with user_id and expiration time
            token = jwt.encode(
                {
                    'user_id': self.id,
                    'email': self.email,  # Always include email in token
                    'exp': datetime.utcnow() + timedelta(hours=1)
                },
                current_app.config['SECRET_KEY'],
                algorithm='HS256'
            )
            
            # Store the token in Redis with expiration
            set_cache(f"reset_token:{token}", str(self.id), ex=3600)  # 1 hour expiration
            
            return token
        except Exception as e:
            current_app.logger.error(f"Error generating reset token: {str(e)}")
            raise

    @classmethod
    def verify_reset_token(cls, token):
        """Verify password reset token."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            user = cls.get_by_id(payload['user_id'])
            if user and user.email == payload.get('email'):  # Verify email matches
                return user
            return None
        except Exception as e:
            logging.error(f"Error verifying reset token: {e}")
            return None

    @classmethod
    def create_table(cls):
        """Create the users table if it doesn't exist."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Drop existing table first
            cur.execute("DROP TABLE IF EXISTS users CASCADE;")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN NOT NULL DEFAULT FALSE,
                    is_admin BOOLEAN NOT NULL DEFAULT FALSE
                );
                
                -- Create index on username and email for faster lookups
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """)
            conn.commit()
        except Exception as e:
            logging.error(f"Error creating users table: {e}")
            conn.rollback()
            raise
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def create_user(cls, username, email, password, is_admin=False):
        """
        Create a new user with the given credentials.
        
        Args:
            username (str): Unique username
            email (str): Unique email address
            password (str): Plain text password to be hashed
            is_admin (bool): Whether the user has admin privileges
            
        Returns:
            dict: User information if successful, None if failed
        """
        # Validate password
        is_valid, error_message = cls.validate_password(password)
        if not is_valid:
            logging.error(f"Password validation failed: {error_message}")
            raise ValueError(error_message)

        conn = get_connection()
        cur = conn.cursor()
        try:
            # Hash the password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # Insert the new user
            cur.execute("""
                INSERT INTO users (username, email, password_hash, is_admin)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id, username, email, created_at, is_admin;
            """, (username, email, password_hash.decode('utf-8'), is_admin))
            
            user = dict(zip(
                ['user_id', 'username', 'email', 'created_at', 'is_admin'],
                cur.fetchone()
            ))
            conn.commit()
            return user
            
        except Exception as e:
            logging.error(f"Error creating user: {e}")
            conn.rollback()
            return None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def authenticate(cls, username, password):
        """
        Authenticate a user with username and password.
        
        Args:
            username (str): Username to authenticate
            password (str): Password to verify
            
        Returns:
            dict: User information and JWT token if successful, None if failed
        """
        # Check login attempts
        if not check_login_attempts(username):
            raise ValueError("Too many login attempts. Please try again in 5 minutes.")
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Get user by username
            cur.execute("""
                SELECT user_id, username, email, password_hash, is_admin
                FROM users
                WHERE username = %s AND is_active = TRUE;
            """, (username,))
            
            result = cur.fetchone()
            if not result:
                return None
                
            user_id, username, email, password_hash, is_admin = result
            
            # Verify password
            if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                return None
                
            # Reset login attempts on successful login
            reset_login_attempts(username)
                
            # Update last login
            cur.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP 
                WHERE user_id = %s;
            """, (user_id,))
            
            # Generate JWT token
            token = jwt.encode(
                {
                    'user_id': user_id,
                    'username': username,
                    'is_admin': is_admin,
                    'exp': datetime.utcnow() + current_app.config['JWT_EXPIRATION_DELTA']
                },
                current_app.config['JWT_SECRET_KEY'],
                algorithm='HS256'
            )
            
            conn.commit()
            return {
                'user_id': user_id,
                'username': username,
                'email': email,
                'is_admin': is_admin,
                'token': token
            }
            
        except Exception as e:
            logging.error(f"Error authenticating user: {e}")
            conn.rollback()
            return None
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def get_user_by_id(cls, user_id):
        """Get user information by user ID."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT user_id, username, email, created_at, last_login, is_active, is_admin
                FROM users
                WHERE user_id = %s;
            """, (user_id,))
            
            result = cur.fetchone()
            if not result:
                return None
                
            return dict(zip(
                ['user_id', 'username', 'email', 'created_at', 'last_login', 'is_active', 'is_admin'],
                result
            ))
            
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def deactivate_user(cls, user_id):
        """Deactivate a user account."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE users
                SET is_active = FALSE
                WHERE user_id = %s
                RETURNING user_id;
            """, (user_id,))
            
            success = cur.fetchone() is not None
            conn.commit()
            return success
            
        except Exception as e:
            logging.error(f"Error deactivating user: {e}")
            conn.rollback()
            return False
        finally:
            cur.close()
            release_connection(conn)

    @classmethod
    def generate_reset_token(cls, email):
        """Generate a password reset token for a user and send reset email."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Get user by email
            cur.execute("""
                SELECT user_id, username, email
                FROM users
                WHERE email = %s AND is_active = TRUE;
            """, (email,))
            
            result = cur.fetchone()
            if not result:
                return None
                
            user_id, username, user_email = result
            
            # Generate reset token
            reset_token = jwt.encode(
                {
                    'user_id': user_id,
                    'purpose': 'password_reset',
                    'exp': datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
                },
                current_app.config['JWT_SECRET_KEY'],
                algorithm='HS256'
            )
            
            # Store reset token in cache
            key = f"reset_token:{user_id}"
            set_cache(key, reset_token, ex=3600)  # 1 hour expiry
            
            return {
                'user_id': user_id,
                'username': username,
                'token': reset_token
            }
            
        except Exception as e:
            logging.error(f"Error generating reset token: {e}")
            return None
        finally:
            cur.close()
            release_connection(conn)
            
    @classmethod
    def verify_reset_token(cls, token):
        """Verify a password reset token."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            if payload.get('purpose') != 'password_reset':
                return None
                
            user_id = payload.get('user_id')
            if not user_id:
                return None
                
            # Check if token matches stored token
            key = f"reset_token:{user_id}"
            stored_token = get_cache(key)
            if not stored_token or stored_token != token:
                return None
                
            return user_id
            
        except jwt.InvalidTokenError:
            return None
            
    @classmethod
    def reset_password(cls, token, new_password):
        """Reset user's password using a reset token."""
        # Validate new password
        is_valid, error_message = cls.validate_password(new_password)
        if not is_valid:
            raise ValueError(error_message)
            
        user_id = cls.verify_reset_token(token)
        if not user_id:
            raise ValueError("Invalid or expired reset token")
            
        # Update password
        if not cls.update_password(user_id, new_password):
            raise ValueError("Failed to update password")
            
        # Clear reset token
        key = f"reset_token:{user_id}"
        set_cache(key, None)
        
        return True

    @classmethod
    def delete_by_id(cls, user_id):
        """Delete user account by ID."""
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                DELETE FROM users
                WHERE user_id = %s;
            """, (user_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logging.error(f"Error deleting user: {e}")
            raise
        finally:
            cur.close()
            release_connection(conn) 