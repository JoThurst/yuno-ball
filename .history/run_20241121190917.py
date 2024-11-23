"""
Module: Run Flask Application

This module initializes and runs a Flask application by creating an instance
of the app using the `create_app` factory function.

Usage:
- This script is intended to be executed as the main entry point of a Flask 
application.
- It imports the `create_app` function from the `app` module, which sets up 
and configures the Flask application.

Functions:
- `create_app()`: Factory function to create and configure the Flask application instance.

Attributes:
- `app`: The Flask application instance created by `create_app`.

Execution:
- When this script is run as the main module, it starts the Flask development server with `debug=True`.
- Example: Run the script using `python run.py` to start the application.

Note:
- Debug mode (`debug=True`) should be used only during development and not in a production environment.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
