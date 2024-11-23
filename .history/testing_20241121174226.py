"""
This module demonstrates connecting to a PostgreSQL database using the psycopg2 library.

Features:
- Connects to a PostgreSQL database using user-provided credentials.
- Handles exceptions to ensure errors during the connection process are logged without crashing the program.
- Provides user feedback on connection success or failure.

Usage:
Ensure that the PostgreSQL server is running and the connection parameters (host, port, user, password, database) are correct.
Replace placeholder values with actual credentials before running the script.
"""

import psycopg2

def connect_to_postgres(database, host, user, password, port):
    """
    Attempts to establish a connection to a PostgreSQL database.
   
    Args:
        database (str): Name of the PostgreSQL database.
        host (str): Hostname or IP address of the PostgreSQL server.
        user (str): Username for authentication.
        password (str): Password for authentication.
        port (str): Port number on which the PostgreSQL server is running.

    Returns:
        psycopg2.extensions.connection: Database connection object if successful.
        None: If the connection fails.
    """
    try:
        conn = psycopg2.connect(
            database=database,
            host=host,
            user=user,
            password=password,
            port=port
        )
        print("Connection successful!")
        return conn
    except psycopg2.OperationalError as e:
        print(f"Operational Error: {e}")
    except psycopg2.Error as e:
        print(f"Database Error: {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")
    return None

# Example usage (replace with actual values before running):
if __name__ == "__main__":
    conn = connect_to_postgres(
        database="postgres",
        host="73.159.20.15",
        user="sean",
        password="password",
        port="5432"
    )
