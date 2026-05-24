"""
Minimal WS test script - run directly to see all output.
"""
import sys
sys.path.insert(0, '/home/ubuntu/.hermes/profiles/coder/workspace/Trading/backend')

from fastapi import FastAPI, WebSocket
from fastapi.routing import APIRouter
from starlette.testclient import TestClient

manager_active = {}

async def simple_connect(websocket: WebSocket, symbols):
    for symbol in symbols:
        if symbol not in manager_active:
            manager_active[symbol] = []
        manager_active[symbol].append(websocket)

def simple_disconnect(websocket: WebSocket, symbols):
    for symbol in symbols:
        if symbol in manager_active and websocket in manager_active[symbol]:
            manager_active[symbol].remove(websocket)

router = APIRouter()

@router.websocket("/ws/prices")
async def prices_ws(websocket: WebSocket):
    symbols = []
    try:
        msg = await websocket.receive_json()
        action = msg.get("action", "")
        print(f"[WS HANDLER] received: {msg}")
        if action == "subscribe":
            raw_symbols = msg.get("symbols", [])
            symbols = [s.replace("/", "") if "/" not in s else s for s in raw_symbols]
        await simple_connect(websocket, symbols)
        await websocket.send_json({"type": "connected", "symbols": symbols})
        print(f"[WS HANDLER] sent connected message")
        while True:
            msg = await websocket.receive_json()
            print(f"[WS HANDLER] received in loop: {msg}")
    except Exception as e:
        print(f"[WS HANDLER] Exception: {type(e).__name__}: {e}")
    finally:
        simple_disconnect(websocket, symbols)

app = FastAPI()
app.include_router(router)

print("Starting TestClient...")
with TestClient(app, base_url="http://test") as client:
    print("Connecting to /ws/prices...")
    with client.websocket_connect("/ws/prices") as ws:
        print("Connected! Sending subscribe...")
        ws.send_json({"action": "subscribe", "symbols": ["BTC/USDT"]})
        print("Waiting for message...")
        msg = ws.receive_json()
        print(f"SUCCESS: {msg}")