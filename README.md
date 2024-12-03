# NBA Sports Analytics Dashboard

This project is a sports analytics dashboard for NBA data. It provides detailed player and team statistics, along with interactive filtering and visualization capabilities.

## Features

- Ingest player and team data from the NBA API.
- Store data in a PostgreSQL database with schemas for development, staging, and production environments.
- Interactive web-based dashboard built with Flask and Tailwind CSS.
- Filterable and sortable statistics for players and teams.

## Requirements

- Python 3.9+
- PostgreSQL
- [nba_api](https://github.com/swar/nba_api)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/JoThurst/nba-sports-analytics.git
cd nba-sports-analytics
```
### 2. Set up a virtual enviornment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
### 3. Install dependencies 
```bash
pip install -r requirements.txt
```
### 4. Setup PostgreSQL
- Create a database named nba_stats.
- Create schemas for develop, staging, and production.
- Grant appropriate privileges to your users.
### 5. Configure the database
Local Configuration : Create file named "db_config.py"
```bash 
import psycopg2
from psycopg2 import sql

def get_connection(schema="develop"):
    """Establish and return a database connection."""
    conn = psycopg2.connect(
        database="postgres",
        host="localhost",
        user="postgres",
        password="password",
        port="5432"
    )
    cur = conn.cursor()
    cur.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(schema)))
    conn.commit()
    return conn
```
Cloud configuration : Create file named "db_config.py"
```bash
import psycopg2
from psycopg2 import sql, pool

DATABASE_URL = "<Your DB Connection URL>"

def get_connection(schema="develop"):
    """Establish and return a database connection."""
    connection_pool = pool.SimpleConnectionPool(
        1,
        10,
        DATABASE_URL
    )
    if connection_pool:
        print("Connection pool created successfully")
    conn = connection_pool.getconn()

    cur = conn.cursor()
    cur.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(schema)))
    conn.commit()
    return conn
```
### 6. Run the ingestion scripts
Fetch Players/Stats
```bash
python ingest_data.py
```
### 7. Run the Flask app
```bash
python run.py
```

### Contribution
## Fork the repository
Create a new branch for your feature or bugfix:
```bash
git checkout -b feature-name
```
Commit your changes and push to your fork
```bash
git add .
git commit -m "Description of changes"
git push origin feature-name
```
Submit a pull request describing your changes