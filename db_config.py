import psycopg2
from psycopg2 import sql, pool
import time
import logging
from contextlib import contextmanager
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool configuration
POOL_MIN_CONN = 2
POOL_MAX_CONN = 20
POOL_IDLE_TIMEOUT = 240
MAX_CONNECTION_AGE = 600
MAX_RETRIES = 3

class DatabaseError(Exception):
    """Custom exception for database errors"""
    pass

def retry_on_connection_error(max_retries=3):
    """Decorator to retry operations on connection errors"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    last_error = e
                    logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (attempt + 1))
                        continue
            raise DatabaseError(f"Max retries exceeded: {str(last_error)}")
        return wrapper
    return decorator

class ManagedConnectionPool(pool.SimpleConnectionPool):
    """Enhanced connection pool with connection validation and age tracking"""
    def __init__(self, minconn, maxconn, *args, **kwargs):
        super().__init__(minconn, maxconn, *args, **kwargs)
        self._connection_times = {}
        self._connection_keys = {}
        self._connection_schemas = {}
        self._pool = {}  # Add explicit pool tracking
        self._last_validation = time.time()
        self._dsn = args[0] if args else kwargs.get('dsn')
        self._connect_kwargs = {
            'dsn': self._dsn,
            'keepalives': kwargs.get('keepalives', 1),
            'keepalives_idle': kwargs.get('keepalives_idle', 30),
            'keepalives_interval': kwargs.get('keepalives_interval', 10),
            'keepalives_count': kwargs.get('keepalives_count', 5),
            'connect_timeout': kwargs.get('connect_timeout', 3),
            'application_name': kwargs.get('application_name', 'yunoball')
        }

    def _init_pool_key(self, key):
        """Initialize a pool for a specific key if it doesn't exist"""
        if key not in self._pool:
            self._pool[key] = []
            # Create initial connections for this key
            for _ in range(self.minconn):
                try:
                    conn = psycopg2.connect(**self._connect_kwargs)
                    self._pool[key].append(conn)
                except Exception as e:
                    logger.error(f"Error creating initial connection for key {key}: {e}")

    def _validate_connection(self, conn):
        """Validate a single connection"""
        try:
            if conn is None or conn.closed:
                return False
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                cur.fetchone()
                return True
        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return False

    def _reset_connection(self, conn, schema="public"):
        """Reset connection state"""
        try:
            if conn and not conn.closed:
                if conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                    conn.rollback()
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(schema)))
                    conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error resetting connection: {e}")
            return False
        return False

    def getconn(self, key=None, schema="public"):
        """Enhanced connection acquisition with validation and recycling"""
        if key is None:
            key = f"{schema}_conn"

        try:
            # Initialize pool for this key if needed
            if key not in self._pool:
                self._init_pool_key(key)

            # Try to get a connection from the pool
            conn = None
            while self._pool[key] and not conn:
                candidate = self._pool[key].pop()
                if self._validate_connection(candidate):
                    conn = candidate
                else:
                    try:
                        candidate.close()
                    except Exception:
                        pass

            # If no valid connection found, create a new one
            if not conn:
                conn = psycopg2.connect(**self._connect_kwargs)

            # Store connection metadata
            conn_id = id(conn)
            self._connection_keys[conn_id] = key
            self._connection_schemas[conn_id] = schema
            self._connection_times[conn_id] = time.time()

            # Reset connection state
            if not self._reset_connection(conn, schema):
                raise DatabaseError("Failed to reset connection state")

            return conn

        except Exception as e:
            logger.error(f"Error getting connection for key {key}: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            raise

    def putconn(self, conn, key=None):
        """Enhanced connection return with validation"""
        if conn is None:
            return

        try:
            conn_id = id(conn)
            original_key = self._connection_keys.get(conn_id)
            
            if original_key is None:
                schema = self._connection_schemas.get(conn_id, "public")
                original_key = key if key is not None else f"{schema}_conn"
                logger.debug(f"Using fallback key {original_key} for connection {conn_id}")

            # Initialize pool for this key if needed
            if original_key not in self._pool:
                self._init_pool_key(original_key)

            if self._validate_connection(conn):
                try:
                    if self._reset_connection(conn, self._connection_schemas.get(conn_id, "public")):
                        # Only add to pool if we haven't exceeded maxconn
                        if len(self._pool[original_key]) < self.maxconn:
                            self._pool[original_key].append(conn)
                        else:
                            self._close_conn(conn)
                    else:
                        self._close_conn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool for key {original_key}: {e}")
                    self._close_conn(conn)
            else:
                self._close_conn(conn)

            # Clean up tracking
            self._connection_times.pop(conn_id, None)
            self._connection_keys.pop(conn_id, None)
            self._connection_schemas.pop(conn_id, None)

        except Exception as e:
            logger.error(f"Error in putconn: {e}")
            self._close_conn(conn)

    def _close_conn(self, conn):
        """Safely close a connection"""
        if conn:
            try:
                conn_id = id(conn)
                self._connection_times.pop(conn_id, None)
                self._connection_keys.pop(conn_id, None)
                self._connection_schemas.pop(conn_id, None)
                if not conn.closed:
                    if conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

    def closeall(self):
        """Close all connections in all pools"""
        for key in list(self._pool.keys()):
            while self._pool[key]:
                conn = self._pool[key].pop()
                self._close_conn(conn)
        self._pool.clear()
        self._connection_times.clear()
        self._connection_keys.clear()
        self._connection_schemas.clear()

# Global connection pool instance
connection_pool = None

def init_db(database_url):
    """Initialize the database connection pool."""
    global connection_pool
    
    if 'neon.tech' in database_url and 'sslmode=' not in database_url:
        database_url += '?sslmode=require'
    
    try:
        connection_pool = ManagedConnectionPool(
            POOL_MIN_CONN,
            POOL_MAX_CONN,
            database_url,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
            connect_timeout=3,
            application_name='yunoball'
        )
        logger.info("Connection pool created successfully")
    except Exception as e:
        logger.error(f"Error creating connection pool: {e}")
        raise

@contextmanager
def get_db_connection(schema="public"):
    """Context manager for database connections"""
    conn = None
    key = f"{schema}_conn"
    try:
        conn = get_connection(schema=schema, key=key)
        yield conn
        if conn and not conn.closed:
            try:
                conn.commit()
            except Exception as e:
                logger.error(f"Error committing transaction: {e}")
                conn.rollback()
                raise
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        if conn and not conn.closed:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            release_connection(conn, key)

@retry_on_connection_error(max_retries=MAX_RETRIES)
def get_connection(schema="public", key=None):
    """Get a validated database connection from the pool and set schema."""
    if not connection_pool:
        raise DatabaseError("Connection pool is not initialized")

    if key is None:
        key = f"{schema}_conn"

    conn = None
    try:
        conn = connection_pool.getconn(key=key, schema=schema)
        if not conn:
            raise DatabaseError("Failed to get connection from pool")
        return conn
    except Exception as e:
        logger.error(f"Error getting connection with key {key}: {str(e)}")
        if conn:
            try:
                connection_pool.putconn(conn, key)
            except Exception:
                if not conn.closed:
                    conn.close()
        raise DatabaseError(f"Failed to get database connection: {str(e)}")

def release_connection(conn, key=None):
    """Release the connection back to the pool."""
    if not conn:
        return

    if not connection_pool:
        logger.warning("Connection pool is not initialized, closing connection directly")
        try:
            if not conn.closed:
                conn.close()
        except Exception:
            pass
        return

    try:
        connection_pool.putconn(conn, key)
    except Exception as e:
        logger.error(f"Error releasing connection to pool: {str(e)}")
        # If we can't return it to the pool, ensure it's at least closed
        try:
            if not conn.closed:
                conn.close()
        except Exception:
            pass

def close_pool():
    """Close all connections in the pool."""
    if connection_pool:
        connection_pool.closeall()
        logger.info("Connection pool closed")


