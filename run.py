"""
Main entry point for the NBA Sports Analytics application.
This script initializes and runs the Flask application in debug mode.
The application is created using the create_app factory function from
the app module.
Usage:
    python run.py
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
