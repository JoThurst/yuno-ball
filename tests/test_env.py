from dotenv import load_dotenv
import os

load_dotenv()

# Print some key environment variables
print("Environment Variables:")
print(f"FORCE_PROXY: {os.getenv('FORCE_PROXY')}")
print(f"FORCE_LOCAL: {os.getenv('FORCE_LOCAL')}")
print(f"PROXY_ENABLED: {os.getenv('PROXY_ENABLED')}")
print(f"BASE_URL: {os.getenv('BASE_URL')}")
print(f"API_KEY: {os.getenv('API_KEY', '[not set]')}") 