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
