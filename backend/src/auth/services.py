from typing import TYPE_CHECKING
from urllib import parse

import httpx

from backend.src.auth.infrastructure import Infrastructure
from backend.src.auth.schemas import Code, AuthTokens, YandexUserData
from backend.src.config import config


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class Service:
    def __init__(self, session: AsyncSession = None):
        self.repository = Infrastructure(session)

    async def generate_yandex_oauth_redirect_url(self):
        query_params = {
            "response_type": "code",
            "client_id": config.yandex_auth.CLIENT_ID,
            "redirect_uri": config.yandex_auth.REDIRECT_URI,
        }

        query_string = parse.urlencode(query_params, quote_via=parse.quote)
        base_url = "https://oauth.yandex.ru/authorize"
        return f"{base_url}?{query_string}"

    async def get_yandex_tokens(self, code: Code) -> AuthTokens:
        code: str = code.model_dump()["code"]
        base_url = "https://oauth.yandex.ru/token"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config.yandex_auth.CLIENT_ID,
            "client_secret": config.yandex_auth.CLIENT_SECRET
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=base_url,
                headers=headers,
                data=data
            )

            tokens = response.json()

        tokens = AuthTokens(**tokens)

        return tokens

    async def get_yandex_user_data(self, access_token: str):
        base_url = "https://login.yandex.ru/info"
        headers = {"Authorization": f"OAuth {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url=f"{base_url}",
                headers=headers
            )

            user_data: dict = response.json()

        user_data = YandexUserData(**user_data)

        return user_data

    async def register_user(self):
        ...
