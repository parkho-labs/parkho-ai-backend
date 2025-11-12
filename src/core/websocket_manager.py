import json
from typing import Dict, List, Optional, Set
from datetime import datetime

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class WebSocketManager:
    def __init__(self):
        self._user_connections: Dict[str, List[WebSocket]] = {}
        self._job_to_user: Dict[int, str] = {}
        self._connection_metadata: Dict[WebSocket, Dict] = {}
        self._job_connection_state: Dict[int, bool] = {}

    async def connect_user(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self._user_connections:
            self._user_connections[user_id] = []

        self._user_connections[user_id].append(websocket)

        self._connection_metadata[websocket] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "jobs_subscribed": set()
        }

    async def disconnect_user(self, websocket: WebSocket) -> None:
        if websocket not in self._connection_metadata:
            return

        user_id = self._connection_metadata[websocket]["user_id"]

        if user_id in self._user_connections:
            self._user_connections[user_id].remove(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        del self._connection_metadata[websocket]

    async def subscribe_to_job(self, websocket: WebSocket, job_id: int, user_id: str) -> None:
        if websocket in self._connection_metadata:
            self._connection_metadata[websocket]["jobs_subscribed"].add(job_id)
            self._job_to_user[job_id] = user_id
            self._job_connection_state[job_id] = True

    async def broadcast_to_job(self, job_id: int, message: Dict) -> None:
        user_id = self._job_to_user.get(job_id)
        if not user_id or user_id not in self._user_connections:
            self._job_connection_state[job_id] = False
            return

        message_with_meta = {
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            **message
        }

        message_json = json.dumps(message_with_meta)
        dead_connections = []
        for websocket in self._user_connections[user_id]:
            if job_id in self._connection_metadata[websocket]["jobs_subscribed"]:
                try:
                    await websocket.send_text(message_json)
                except Exception as e:
                    self._job_connection_state[job_id] = False
                    dead_connections.append(websocket)
                    raise Exception(e)

        for dead_ws in dead_connections:
            await self.disconnect_user(dead_ws)

    async def broadcast_to_user(self, user_id: str, message: Dict) -> None:
        if user_id not in self._user_connections:
            return

        message_with_meta = {
            "timestamp": datetime.utcnow().isoformat(),
            **message
        }

        message_json = json.dumps(message_with_meta)
        dead_connections = []

        for websocket in self._user_connections[user_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                dead_connections.append(websocket)
                raise Exception(e)

        for dead_ws in dead_connections:
            await self.disconnect_user(dead_ws)

    def get_user_connections(self, user_id: str) -> List[WebSocket]:
        return self._user_connections.get(user_id, [])

    def is_user_connected(self, user_id: str) -> bool:
        return user_id in self._user_connections and len(self._user_connections[user_id]) > 0

    def is_job_connection_alive(self, job_id: int) -> bool:
        return self._job_connection_state.get(job_id, False)

    def get_connected_users(self) -> List[str]:
        return list(self._user_connections.keys())

    def _get_total_connections(self) -> int:
        return sum(len(connections) for connections in self._user_connections.values())

    def get_stats(self) -> Dict:
        return {
            "total_connections": self._get_total_connections(),
            "connected_users": len(self._user_connections),
            "jobs_tracked": len(self._job_to_user),
            "users": list(self._user_connections.keys())
        }


# Global WebSocket manager instance
websocket_manager = WebSocketManager()