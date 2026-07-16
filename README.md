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
- Node.js and npm (for Tailwind CSS)
- [nba_api](https://github.com/swar/nba_api)

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/JoThurst/nba-sports-analytics.git
cd nba-sports-analytics

```

### 2. Set up a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt

```

### 4. Install Node.js and Tailwind CSS dependencies

Ensure you have Node.js installed. Then install the necessary Tailwind CSS dependencies:

```bash
npm install

```

This installs `tailwindcss`, `postcss`, and `autoprefixer`.

---

## Tailwind CSS Setup and Development

Tailwind CSS is used for styling the application. Here's how to set up and use it during development:

### 1. Initialize Tailwind CSS

Tailwind is already set up in this project, but if you need to reinitialize it, run:

```bash
npx tailwindcss init

```

### 2. Build Tailwind CSS

To generate the compiled `output.css` file from the `tailwind.css` source, run:

```bash
npm run build:css

```

The compiled CSS file will be saved in `app/static/css/output.css`.

### 3. Watch for Changes

During development, you can watch for changes to your Tailwind CSS and Flask template files to rebuild the CSS automatically:

```bash
npm run watch:css

```

### 4. Customize Tailwind CSS

To customize the Tailwind configuration, edit the `tailwind.config.js` file in the root of the project. For example, you can extend the theme or add custom plugins:

```javascript
module.exports = {
  content: [
    './app/templates/**/*.html',
    './app/static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        customGray: '#2A2A2A',
      },
    },
  },
  plugins: [],
};

```

---

## Database Setup

### 1. Set up PostgreSQL

- Create a database named `nba_stats`.
- Create schemas for `develop`, `staging`, and `production`.
- Grant appropriate privileges to your users.

### 2. Configure the database

#### Local Configuration (`db_config.py`)

```python
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

def release_connection(conn):
    """Release the connection back to the pool."""
    if connection_pool and conn:
        connection_pool.putconn(conn)

def close_pool():
    """Close all connections when shutting down the app."""
    if connection_pool:
        connection_pool.closeall()

```

#### Cloud Configuration (`db_config.py`)

```python
import psycopg2
from psycopg2 import sql, pool

DATABASE_URL = "<YOUR-CONNECTION-STRING>"

# Initialize the connection pool globally
connection_pool = pool.SimpleConnectionPool(
    1, 10, DATABASE_URL
)

if connection_pool:
    print("Connection pool created successfully")

def get_connection(schema="public"):
    """Get a database connection from the pool and set schema."""
    if not connection_pool:
        raise Exception("Connection pool is not initialized")

    conn = connection_pool.getconn()
    cur = conn.cursor()
    cur.execute(sql.SQL("SET search_path TO {};").format(sql.Identifier(schema)))
    conn.commit()
    return conn

def release_connection(conn):
    """Release the connection back to the pool."""
    if connection_pool and conn:
        connection_pool.putconn(conn)

def close_pool():
    """Close all connections when shutting down the app."""
    if connection_pool:
        connection_pool.closeall()

```

---

## Configuration

### Application Configuration

The application uses a centralized configuration system in `app/config.py`. This handles:
- Database connections
- JWT authentication
- API keys
- Environment-specific settings (development/production/testing)

To set up the configuration:

1. Copy the example configuration:
```bash
cp app/config.example.py app/config.py
```

2. Set required environment variables:
```bash
export FLASK_ENV=development  # or production
export JWT_SECRET_KEY=your-secure-secret-key
export SECRET_KEY=your-flask-secret-key
```

3. Update the configuration values in `app/config.py`:
- `DATABASE_URL`: Your PostgreSQL connection string
- `API_KEY`: Your API key for protected endpoints
- Other environment-specific settings

### Authentication Setup

To set up user authentication:

1. Initialize the users table:
```bash
flask db init-users
```

2. Create an admin user:
```bash
flask db create-admin
```

3. Create regular users:
```bash
flask db create-user
```

---

## Running the Application

### 1. Run the ingestion scripts

Fetch and store players:

```bash
python ingest_data.py

```

### 2. Run the Flask app

```bash
python run.py

```

---

## Contribution

### Fork the repository

Create a new branch for your feature or bugfix:

```bash
git checkout -b feature-name

```

Commit your changes and push to your fork:

```bash
git add .
git commit -m "Description of changes"
git push origin feature-name

```

Submit a pull request describing your changes.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
