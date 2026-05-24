"""Minimal WS test via socket to avoid TestClient hangs."""
import socket, base64, os, time

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
print('Response:')
print(resp.decode()[:500])
s.close()