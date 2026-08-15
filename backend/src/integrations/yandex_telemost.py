import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status

from backend.src.auth.models import OAuthAccount, OAuthEnum
from backend.src.config import config

logger = logging.getLogger(__name__)

TELEMOST_CREATE_URL = (
    "https://cloud-api.yandex.net/v1/telemost-api/conferences"
)
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
TELEMOST_SCOPE = "telemost-api:conferences.create"
CALENDAR_SCOPE = "calendar:all"
YANDEX_LOGIN_SCOPES = "login:info login:email"
YANDEX_INTEGRATION_SCOPES = f"{YANDEX_LOGIN_SCOPES} {CALENDAR_SCOPE}"


def oauth_is_yandex(account: OAuthAccount) -> bool:
    provider = account.provider
    if provider == OAuthEnum.YANDEX:
        return True
    return str(provider).upper() in {"YANDEX", "OAUTHENUM.YANDEX"}


def yandex_account_from_user(user) -> OAuthAccount | None:
    accounts = getattr(user, "oauth_accounts", None) or []
    for account in accounts:
        if oauth_is_yandex(account):
            return account
    return None


def has_telemost_scope(account: OAuthAccount | None) -> bool:
    if not account or not account.access_token:
        return False
    return TELEMOST_SCOPE in (account.scopes or "")


async def refresh_yandex_access_token(account: OAuthAccount) -> str:
    if not account.refresh_token:
        if account.access_token:
            return account.access_token
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yandex is not connected",
        )

    expires = account.token_expires_at
    now = datetime.now(timezone.utc)
    if (
        account.access_token
        and expires
        and expires - timedelta(minutes=5) > now
    ):
        return account.access_token

    data = {
        "grant_type": "refresh_token",
        "refresh_token": account.refresh_token,
        "client_id": config.yandex_auth.CLIENT_ID,
        "client_secret": config.yandex_auth.CLIENT_SECRET,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(YANDEX_TOKEN_URL, data=data)
        payload = response.json()

    access = payload.get("access_token")
    if not access:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yandex token expired, connect Yandex again",
        )

    account.access_token = access
    if payload.get("refresh_token"):
        account.refresh_token = payload["refresh_token"]
    expires_in = int(payload.get("expires_in") or 0)
    if expires_in:
        account.token_expires_at = now + timedelta(seconds=expires_in)
    return access


async def create_telemost_conference(account: OAuthAccount) -> str:
    if not has_telemost_scope(account):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect Yandex Telemost in profile integrations",
        )

    token = await refresh_yandex_access_token(account)
    headers = {
        "Authorization": f"OAuth {token}",
        "Content-Type": "application/json",
    }
    body = {"waiting_room_level": "PUBLIC"}

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            TELEMOST_CREATE_URL, headers=headers, json=body
        )
        payload = response.json() if response.content else {}

    if response.status_code == 403 or payload.get("error") == (
        "ApiRestrictedToOrganizations"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Telemost API is only for Yandex 360 for Business. "
                "Paste a link from telemost.yandex.ru"
            ),
        )

    join_url = payload.get("join_url")
    if response.status_code >= 400 or not join_url:
        logger.warning("telemost create failed %s %s", response.status_code, payload)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create Telemost room",
        )
    return join_url
