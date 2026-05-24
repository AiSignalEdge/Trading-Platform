"""Ultra-minimal WebSocket test — no auth, no logic."""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/test")
async def minimal_ws(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"type": "connected"})
    logger.info("WS test: sent initial message")
    try:
        msg = await websocket.receive_json()
        logger.info(f"WS test: got {msg}")
    except WebSocketDisconnect:
        logger.info("WS test: disconnected")
    except Exception as e:
        logger.error(f"WS test: error {e}")
    finally:
        await websocket.close()
        logger.info("WS test: closed")