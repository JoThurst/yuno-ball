
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

----------

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

----------

## Database Setup

### 1. Set up PostgreSQL

-   Create a database named `nba_stats`.
-   Create schemas for `develop`, `staging`, and `production`.
-   Grant appropriate privileges to your users.

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

```

#### Cloud Configuration (`db_config.py`)

```python
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

----------

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

----------

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

----------

## License

This project is licensed under the MIT License. See the LICENSE file for details.


