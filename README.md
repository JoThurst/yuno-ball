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

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/nba-sports-analytics.git
   cd nba-sports-analytics
   ```

2. **Set Up a virtual enviornment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

    ```
3. **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4. **Setup PostgreSQL**:
    Create a database named "nba_stats"
    Create schemas for develop staging and production
    Grant appropriate privedges to your users

5. **Configure the Database**:
    Create a db_config.py file:
    ```python
    import psycopg2
    from psycopg2 import sql

    def get_connection(schema = "develop"):
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

6. **Run the ingestion scripts**:
    Fetch and store players:
    ```bash
    python ingest_data.py
    ```
7. **Run the Flask App**:
    ```bash
    python run.py
    ```
    **Contribution**
    Fork the repository
    Create a new branch for your feature or bugfix
    ```bash
    git checkout -b feature-name
    ```

    Commit your changes and push to your fork
    ```bash
    git add . 
    git commit -m "Description of changes"
    git push origin feature-name
    ```

    
