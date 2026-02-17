"""WebSocket endpoint for real-time event streaming."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from aegis.services.notifier import notifier

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await notifier.connect(websocket)
    try:
        while True:
            # Keep connection alive — client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        notifier.disconnect(websocket)
