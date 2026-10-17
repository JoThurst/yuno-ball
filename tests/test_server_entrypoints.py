"""The server entrypoints must match their configured server protocols."""

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

from asgiref.wsgi import WsgiToAsgi
from flask import Flask


ROOT = Path(__file__).resolve().parents[1]


def _load_entrypoint(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wsgi_entrypoint_exports_flask_without_changing_network_policy(monkeypatch):
    flask_app = Flask(__name__)
    package = ModuleType("app")
    package.create_app = lambda: flask_app
    monkeypatch.setitem(sys.modules, "app", package)
    monkeypatch.setenv("PROXY_ENABLED", "false")
    monkeypatch.setenv("FORCE_PROXY", "false")
    monkeypatch.setenv("FORCE_LOCAL", "true")

    entrypoint = _load_entrypoint("wsgi")

    assert entrypoint.app is flask_app
    assert entrypoint.application is flask_app
    assert os.environ["PROXY_ENABLED"] == "false"
    assert os.environ["FORCE_PROXY"] == "false"
    assert os.environ["FORCE_LOCAL"] == "true"


def test_asgi_entrypoint_wraps_wsgi_app(monkeypatch):
    flask_app = Flask(__name__)
    wsgi_module = ModuleType("wsgi")
    wsgi_module.app = flask_app
    monkeypatch.setitem(sys.modules, "wsgi", wsgi_module)

    entrypoint = _load_entrypoint("asgi")

    assert isinstance(entrypoint.app, WsgiToAsgi)
    assert entrypoint.app.wsgi_application is flask_app
