"""WSGI entrypoint for Gunicorn.

Runtime network policy comes from the configured environment, not imports.
"""

from app import create_app

app = create_app()
application = app
