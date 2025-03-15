import os
import sys

# Add the application directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for proxy configuration
os.environ["PROXY_ENABLED"] = "true"
os.environ["FORCE_PROXY"] = "true"

# Import the app
from app import create_app
application = create_app()

# For Gunicorn
app = application 