"""
Test WebSocket + Middleware interaction.
"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
import asyncio

class TestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print(f"[TEST MIDDLEWARE] path={request.url.path!r} upgrade={request.headers.get('upgrade', '')!r}")
        return await call_next(request)

app = FastAPI()
app.add_middleware(TestMiddleware)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.websocket("/prices")
async def ws_prices(websocket):
    await websocket.accept()
    await websocket.send_json({"type": "connected"})
    msg = await websocket.receive_json()
    await websocket.send_json({"type": "subscribed", **msg})

client = TestClient(app)

# Test WS connection
with client.websocket_connect("/prices") as ws:
    ws.send_json({"action": "subscribe", "symbols": ["BTC/USDT"]})
    data = ws.receive_json()
    print("Received:", data)
print("WS test passed!")