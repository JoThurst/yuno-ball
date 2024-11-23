import psycopg2

try:
    conn = psycopg2.connect(
        database="postgres",
        host="73.159.20.15",
        user="sean",
        password="password",
        port="5432"
    )
    print("Connection successful!")
except Exception as e:
    print(f"Error: {e}")
