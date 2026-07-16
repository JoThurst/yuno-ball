import os
from dotenv import load_dotenv
import psycopg2
from pathlib import Path

def optimize_database():
    """Execute database optimizations by creating indexes."""
    # Load environment variables
    load_dotenv()
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Connect to database
    print("Connecting to database...")
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    
    try:
        # Read and execute optimization script
        script_path = Path(__file__).parent / 'optimize_database.sql'
        with open(script_path, 'r') as f:
            sql_script = f.read()
        
        print("Creating indexes...")
        cur.execute(sql_script)
        conn.commit()
        print("Database optimization completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during optimization: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    optimize_database() 