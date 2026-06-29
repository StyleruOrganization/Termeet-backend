from urllib import parse
from typing import TYPE_CHECKING

import httpx
from fastapi import HTTPException, status

from backend.src.config import config
from backend.src.users.infrastructures import Infrastructure

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from backend.src.users.schemas import UserSchema


class Service:
    def __init__(
        self,
        session: AsyncSession = None,
    ):
        self.repository = Infrastructure(session)

    async def generate_yandex_oauth_redirect_url(self):
        scope = "telemost-api:conferences.create telemost-api:conferences.read telemost-api:conferences.update"
        query_params = {
            "response_type": "token",
            "client_id": config.yandex_auth.CLIENT_ID,
            # "redirect_uri": config.yandex_auth.REDIRECT_URI,
            "scope": scope,
            "force_confirm": "yes",
        }

        query_string = parse.urlencode(query_params, quote_via=parse.quote)
        base_url = "https://oauth.yandex.ru/authorize"
        return f"{base_url}?{query_string}"

    async def create_telemost(self, user: UserSchema):
        access_token = "y0__xDE3f3wAxjsyj8g2ePd8hb5wFIjfRRT7sx6fXqrCeL4vpAehQ"
        base_url = "https://cloud-api.yandex.net/v1/telemost-api/conferences"
        data = {
            "waiting_room_level": "PUBLIC",
        }
        headers = {
            "Authorization": f"OAuth {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=base_url, headers=headers, data=data
            )

            response: dict = response.json()

        # backend-local   | {'error': 'FormatterParseError', 'description': 'Unable to parse data.', 'message': 'Не удалось разобрать данные.'}

        # По сути, хуй появится
        if "error" in response:
            print(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Exception from yandex: invalid yandex token",
            )

        join_url = response["join_url"]

        return join_url
