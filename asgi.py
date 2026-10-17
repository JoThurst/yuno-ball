"""ASGI entrypoint for Uvicorn."""

from asgiref.wsgi import WsgiToAsgi

from wsgi import app as flask_app

app = WsgiToAsgi(flask_app)
