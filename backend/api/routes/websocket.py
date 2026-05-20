"""
WebSocket routes for real-time price streams.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections per symbol."""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbols: list[str]):
        await websocket.accept()
        for symbol in symbols:
            if symbol not in self.active_connections:
                self.active_connections[symbol] = []
            self.active_connections[symbol].append(websocket)

    def disconnect(self, websocket: WebSocket, symbols: list[str]):
        for symbol in symbols:
            if symbol in self.active_connections:
                if websocket in self.active_connections[symbol]:
                    self.active_connections[symbol].remove(websocket)

    async def broadcast(self, symbol: str, message: dict):
        if symbol in self.active_connections:
            disconnected = []
            for connection in self.active_connections[symbol]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn, [symbol])


manager = ConnectionManager()


@router.websocket("/ws/prices")
async def prices_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time price streams.
    Client sends: {"action":"subscribe","symbols":["BTC/USDT","ETH/USDT"]}
    Server sends: {"symbol":"BTC/USDT","exchange":"binance","price":81299.14,...}
    """
    symbols: list[str] = []
    try:
        # Wait for subscription message
        msg = await websocket.receive_json()
        action = msg.get("action", "")
        if action == "subscribe":
            raw_symbols = msg.get("symbols", [])
            # Normalize CCXT-style symbols
            symbols = [s.replace("/", "") if "/" not in s else s for s in raw_symbols]
        await manager.connect(websocket, symbols)
        logger.info(f"WebSocket connected for symbols: {symbols}")

        # Send heartbeat every 30s
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(heartbeat())

        while True:
            try:
                msg = await websocket.receive_json()
                action = msg.get("action", "")
                if action == "subscribe":
                    new_syms = msg.get("symbols", [])
                    symbols = [s.replace("/", "") if "/" not in s else s for s in new_syms]
                    await manager.connect(websocket, symbols)
            except WebSocketDisconnect:
                break
            except Exception:
                break

        heartbeat_task.cancel()
    except Exception:
        pass
    finally:
        manager.disconnect(websocket, symbols)


@router.websocket("/ws/ohlcv")
async def ohlcv_websocket(websocket: WebSocket):
    """
    WebSocket for OHLCV candle streams (Binance candle endpoint).
    """
    await websocket.accept()
    logger.info("OHLCV WebSocket connected")
    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action", "")
            if action == "subscribe":
                symbol = msg.get("symbol", "BTC/USDT").replace("/", "")
                timeframe = msg.get("timeframe", "1m")
                await websocket.send_json({
                    "type": "subscribed",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "note": "Binance WebSocket would stream kline data here",
                })
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        logger.info("OHLCV WebSocket disconnected")