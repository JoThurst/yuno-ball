"""
The `socket` module allows the creation and management of sockets for 
network communication, supporting various protocols (e.g., TCP, UDP). 
It enables sending and receiving data across networks and is widely used 
for client-server applications, web communication, and more.

Key Features:
- Create sockets using different address families (e.g., IPv4, IPv6).
- Use various socket types like STREAM (TCP) or DATAGRAM (UDP).
- Bind to specific addresses and ports.
- Establish connections and accept incoming connections.
- Send and receive data over the network.
- Support for low-level network programming.

Typical Usage Example:
    import socket
    
    # Create a TCP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Connect to a server
    s.connect(("example.com", 80))
    
    # Send data
    s.sendall(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
    
    # Receive data
    response = s.recv(1024)
    print(response.decode())
    
    # Close the connection
    s.close()
"""

import socket

HOST = "73.159.20.15"
PORT = 5432

try:
    with socket.create_connection((HOST, PORT), timeout=5):
        print("Connection successful!")
except Exception as e:
    print(f"Connection failed: {e}")
