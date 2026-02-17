"""WebSocket event broadcaster and connection manager."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("aegis.notifier")


class Notifier:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    def broadcast(self, event: str, data: dict[str, Any]):
        """Broadcast an event to all connected WebSocket clients.

        Safe to call from sync context — queues messages for async delivery.
        """
        message = json.dumps({"event": event, "data": data})
        disconnected: list[WebSocket] = []

        for ws in self._connections:
            try:
                # Use the low-level sync send since we may be called from sync context
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(ws.send_text(message))
                except RuntimeError:
                    # No event loop — skip broadcast (happens in tests/sync context)
                    pass
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_async(self, event: str, data: dict[str, Any]):
        """Broadcast from an async context."""
        message = json.dumps({"event": event, "data": data})
        disconnected: list[WebSocket] = []

        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton instance
notifier = Notifier()
