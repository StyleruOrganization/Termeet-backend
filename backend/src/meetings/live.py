import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketDisconnect, WebSocketState

from backend.src.auth.dependencies import (
    get_user_by_token_sub,
    validate_token_type,
)
from backend.src.auth.utils import ACCESS_TOKEN_TYPE, decode_jwt
from backend.src.users.schemas import UserSchema

logger = logging.getLogger(__name__)


async def optional_user_from_token(
    token: str | None, session: AsyncSession
) -> UserSchema | None:
    if not token:
        return None
    try:
        payload = await decode_jwt(token=token)
        await validate_token_type(payload, ACCESS_TOKEN_TYPE)
        user = await get_user_by_token_sub(payload, session)
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None


class MeetLiveHub:
    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._users: dict[WebSocket, UserSchema | None] = {}

    async def connect(
        self,
        meeting_id: str,
        websocket: WebSocket,
        user: UserSchema | None,
    ) -> None:
        await websocket.accept()
        self._rooms[meeting_id].add(websocket)
        self._users[websocket] = user

    def disconnect(self, meeting_id: str, websocket: WebSocket) -> None:
        room = self._rooms.get(meeting_id)
        if room is not None:
            room.discard(websocket)
            if not room:
                self._rooms.pop(meeting_id, None)
        self._users.pop(websocket, None)

    async def publish(self, record, to_response) -> None:
        meeting_id = str(record.id)
        sockets = list(self._rooms.get(meeting_id, ()))
        for websocket in sockets:
            if websocket.client_state != WebSocketState.CONNECTED:
                self.disconnect(meeting_id, websocket)
                continue
            user = self._users.get(websocket)
            body = {
                "type": "meet",
                "meet": to_response(record, user).model_dump(
                    mode="json", by_alias=True
                ),
            }
            try:
                await websocket.send_json(body)
            except Exception:
                logger.exception("meet live send failed")
                self.disconnect(meeting_id, websocket)

    async def keepalive(self, websocket: WebSocket) -> None:
        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                await asyncio.sleep(20)
                await websocket.send_json({"type": "ping"})
        except (WebSocketDisconnect, Exception):
            return


meet_live_hub = MeetLiveHub()
