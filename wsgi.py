import os
import sys

# Add the application directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set environment variables for proxy configuration
os.environ['PROXY_ENABLED'] = 'true'
os.environ['FORCE_PROXY'] = 'true'
os.environ['FORCE_LOCAL'] = 'false'

from app import create_app
from asgiref.wsgi import WsgiToAsgi

# Create the Flask application
flask_app = create_app()

# Wrap the Flask app with ASGI adapter
app = WsgiToAsgi(flask_app)

# Make the app available for both WSGI (gunicorn) and ASGI (uvicorn)
application = app 