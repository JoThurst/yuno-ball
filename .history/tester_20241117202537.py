


HOST = "73.159.20.15"
PORT = 5432

try:
    with socket.create_connection((HOST, PORT), timeout=5):
        print("Connection successful!")
except Exception as e:
    print(f"Connection failed: {e}")
