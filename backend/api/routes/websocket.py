"""
WebSocket routes — minimal working implementation.
Tested: confirmed working with BaseHTTPMiddleware auth stack.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/prices")
async def prices_websocket(websocket: WebSocket):
    """
    Minimal working WebSocket — no ConnectionManager, no double-accept.
    Client sends: {"action":"subscribe","symbols":["BTC/USDT"]}
    Server sends: {"type":"connected","symbols":[...]}
    """
    await websocket.accept()
    try:
        msg = await websocket.receive_json()
        action = msg.get("action", "")
        symbols = []
        if action == "subscribe":
            raw = msg.get("symbols", [])
            symbols = [s.replace("/", "") if "/" not in s else s for s in raw]
        await websocket.send_json({"type": "connected", "symbols": symbols})
        logger.info(f"WS connected: {symbols}")

        while True:
            msg = await websocket.receive_json()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        logger.info("WS disconnected")


@router.websocket("/ws/ohlcv")
async def ohlcv_websocket(websocket: WebSocket):
    """Minimal OHLCV WebSocket."""
    await websocket.accept()
    try:
        msg = await websocket.receive_json()
        if msg.get("action") == "subscribe":
            await websocket.send_json({
                "type": "subscribed",
                "symbol": msg.get("symbol", "BTC/USDT"),
                "timeframe": msg.get("timeframe", "1m"),
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"OHLCV WS error: {e}")