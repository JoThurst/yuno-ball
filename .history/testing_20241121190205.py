"""
This module establishes a connection to a PostgreSQL database using psycopg2,
and sets the search path to a specified schema.

Usage:
- Replace placeholder values (host, user, password, etc.) with actual database credentials.
- Specify the desired schema (default is 'develop') when calling the `get_connection` function.
- The returned connection object can be used for executing queries.

Features:
- Automatically sets the search path to the specified schema.
- Handles common database connection and query errors gracefully.

Raises:
- psycopg2.OperationalError: If the database connection fails.
- psycopg2.Error: If setting the schema search path fails.
- Exception: For any unexpected errors.
"""

import psycopg2
from psycopg2 import sql

try:
    # Establish a connection to the database
    conn = psycopg2.connect(
        database="postgres",
        host="localhost",
        user="postgres",
        password="password",
        port="5432"
    )
    print("Database connection established.")

    # Set the search path to the specified schema
    schema = "develop"
    cur = conn.cursor()
    cur.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(schema)))
    conn.commit()
    print(f"Search path set to schema: {schema}")

except psycopg2.OperationalError as e:
    print(f"Operational Error: Unable to connect to the database. {e}")
    raise  # Re-raise the exception for the calling script to handle

except psycopg2.Error as e:
    print(f"Database Error: Failed to set search path. {e}")
    raise  # Re-raise the exception for the calling script to handle

except Exception as e:
    print(f"Unexpected Error: {e}")
    raise  # Re-raise the exception for the calling script to handle

