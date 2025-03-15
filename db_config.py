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
POOL_MIN_CONN = 2  # Increased minimum connections
POOL_MAX_CONN = 20  # Increased maximum connections
POOL_IDLE_TIMEOUT = 240  # 4 minutes in seconds (below Neon's 5-minute timeout)
MAX_CONNECTION_AGE = 600  # 10 minutes in seconds (more aggressive recycling)
MAX_RETRIES = 3

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
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue
            raise last_error
        return wrapper
    return decorator

class ManagedConnectionPool(pool.SimpleConnectionPool):
    """Enhanced connection pool with connection validation and age tracking"""
    def __init__(self, minconn, maxconn, *args, **kwargs):
        super().__init__(minconn, maxconn, *args, **kwargs)
        self._connection_times = {}
        self._last_validation = time.time()
        # Store connection arguments for recycling
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

    def _validate_connection(self, conn):
        """Validate a single connection"""
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                cur.fetchone()
                return True
        except Exception:
            return False

    @retry_on_connection_error(max_retries=MAX_RETRIES)
    def getconn(self, key=None):
        """Enhanced connection acquisition with validation and recycling"""
        try:
            current_time = time.time()
            
            # Get connection from pool
            conn = super().getconn(key)
            
            # Check if connection needs recycling
            is_old = (current_time - self._connection_times.get(id(conn), 0) > MAX_CONNECTION_AGE)
                
            if is_old or not self._validate_connection(conn):
                try:
                    super().putconn(conn, key)
                    # Use stored connection arguments for recycling
                    conn = psycopg2.connect(**self._connect_kwargs)
                except Exception as e:
                    logger.error(f"Error recycling connection: {e}")
                    raise

            # Set connection properties before any operations
            if conn.status == psycopg2.extensions.STATUS_READY:
                conn.set_session(autocommit=False)
            
            # Track connection time and return valid connection
            self._connection_times[id(conn)] = current_time
            return conn
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise

    def putconn(self, conn, key=None):
        """Enhanced connection return with validation"""
        try:
            if conn and self._validate_connection(conn):
                try:
                    if not conn.closed and conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                        conn.rollback()
                except Exception:
                    pass
                self._connection_times.pop(id(conn), None)
                super().putconn(conn, key)
            else:
                self._close_conn(conn)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {e}")
            self._close_conn(conn)

    def _close_conn(self, conn):
        """Safely close a connection"""
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    def validate_all_connections(self):
        """Validate and refresh all connections in the pool"""
        logger.debug("Starting pool-wide connection validation")
        for i in range(self.minconn):
            try:
                conn = super().getconn()
                if not self._validate_connection(conn):
                    self._close_conn(conn)
                    conn = psycopg2.connect(self._connect_kwargs['dsn'])
                super().putconn(conn)
            except Exception as e:
                logger.error(f"Error during connection validation: {e}")

# Global connection pool instance
connection_pool = None

def init_db(database_url):
    """Initialize the database connection pool."""
    global connection_pool
    
    # Ensure SSL mode for Neon databases
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
    conn_key = f"{schema}_conn"  # Use schema as connection key
    try:
        conn = get_connection(schema, conn_key)
        yield conn
        if not conn.closed:
            conn.commit()
    except Exception:
        if conn and not conn.closed:
            conn.rollback()
        raise
    finally:
        if conn:
            release_connection(conn, conn_key)

@retry_on_connection_error(max_retries=MAX_RETRIES)
def get_connection(schema="public", key=None):
    """Get a validated database connection from the pool and set schema."""
    if not connection_pool:
        raise Exception("Connection pool is not initialized")

    conn = None
    try:
        conn = connection_pool.getconn(key=key)
        
        # Ensure we're not in a transaction before setting search path
        if conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
            conn.rollback()
            
        cur = conn.cursor()
        cur.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(schema)))
        conn.commit()
        return conn
    except Exception as e:
        logger.error(f"Error getting connection: {e}")
        if conn:
            connection_pool.putconn(conn, key=key)
        raise

def release_connection(conn, key=None):
    """Release the connection back to the pool with enhanced validation."""
    if connection_pool and conn:
        connection_pool.putconn(conn, key=key)

def close_pool():
    """Close all connections when shutting down the app."""
    if connection_pool:
        connection_pool.closeall()
        logger.info("Connection pool closed")


