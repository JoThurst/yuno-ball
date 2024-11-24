"""
Application Factory Module.

This module provides the factory function `create_app` for creating and
configuring the Flask application instance. It initializes the Flask app,
registers blueprints, and sets up any necessary configurations required by the
application.
"""

from flask import Flask
from app.routes import main


def create_app():
    """
    Create and configure the Flask application.

    This function initializes the Flask app, registers the main blueprint,
    and performs any necessary configuration. It serves as the factory
    function for creating instances of the Flask application.

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__)
    app.register_blueprint(main)
    return app
