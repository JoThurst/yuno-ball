"""Bounded, non-mutating probes for required application storage."""

import psycopg2


def check_postgres_connection() -> bool:
    """Run a bounded read-only query against the configured PostgreSQL engine."""
    try:
        from app.database import engine

        dsn = engine.url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        connection = psycopg2.connect(
            dsn,
            connect_timeout=3,
            options="-c statement_timeout=1500",
        )
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return cursor.fetchone() == (1,)
        finally:
            connection.close()
    except Exception:
        return False


def check_redis_connection(redis_client) -> bool:
    """Ping the configured Redis client, whose socket timeouts are bounded."""
    try:
        return redis_client.ping() is True
    except Exception:
        return False


def check_readiness(redis_client) -> dict[str, bool]:
    """Return dependency states without exposing exception or URL details."""
    return {
        "postgresql": check_postgres_connection(),
        "redis": check_redis_connection(redis_client),
    }
