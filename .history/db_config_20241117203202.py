"""
This script demonstrates the use of the `psycopg2` library, a PostgreSQL 
database adapter for Python. It provides an interface for interacting 
with PostgreSQL databases, enabling operations like querying, updating, 
and managing database connections.

Key Features:
- Establish connections to PostgreSQL databases.
- Execute SQL queries (SELECT, INSERT, UPDATE, DELETE).
- Support for transactions with commit and rollback functionality.
- Use of server-side cursors for efficient data retrieval.
- Integration with PostgreSQL-specific features such as COPY.
"""

import psycopg2
from psycopg2 import sql


def get_connection(schema="sean"):
    """Establish and return a database connection."""
    conn = psycopg2.connect(
        database="postgres",
        host="73.159.20.15",
        user="sean",
        password="password",
        port="5432"
    )
    cur = conn.cursor()
    cur.execute(sql.SQL("SET search_path TO {};").format(
        sql.Identifier(schema)))
    conn.commit()
    return conn
