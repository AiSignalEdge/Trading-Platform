"""Minimal WS test using requests to confirm server is up, then raw socket for WS."""
import socket, base64, os, sys
sys.path.insert(0, '/home/ubuntu/.hermes/profiles/coder/workspace/Trading/backend')

# First check versions
import uvicorn, fastapi, starlette
print(f"uvicorn={uvicorn.__version__} fastapi={fastapi.__version__} starlette={starlette.__version__}")

# Verify the WS route exists
from main import create_app
app = create_app()
ws_routes = [r for r in app.routes if hasattr(r, 'path') and 'ws/' in r.path]
print(f"WS routes: {[r.path for r in ws_routes]}")

# Now try raw WS handshake
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
s.connect(('127.0.0.1', 8080))
key = base64.b64encode(os.urandom(16)).decode()
http_req = (
    'GET /ws/prices HTTP/1.1\r\n'
    'Host: 127.0.0.1:8080\r\n'
    'Upgrade: websocket\r\n'
    'Connection: Upgrade\r\n'
    'Sec-WebSocket-Key: ' + key + '\r\n'
    'Sec-WebSocket-Version: 13\r\n'
    '\r\n'
)
s.send(http_req.encode())
resp = s.recv(8192)
print('WS /ws/prices response:')
print(resp.decode()[:400])
s.close()