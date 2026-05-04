import asyncio
from datetime import timedelta, datetime, UTC

import jwt
import bcrypt
from aiosmtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.src.config import config

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
VERIFICATION_TOKEN_TYPE = "verification"
TOKEN_TYPE_FIELD = "type"

REFRESH_TOKEN_COOKIE = "refresh_token"


async def create_jwt_token(
    token_type: str,
    token_data: dict,
    expire_minutes: int = config.auth_jwt.ACCESS_TOKEN_EXPIRE_MINUTES,
    expire_timedelta: timedelta | None = None,
) -> str:

    jwt_payload = {TOKEN_TYPE_FIELD: token_type}
    jwt_payload.update(token_data)

    return await encode_jwt(
        jwt_payload,
        expire_minutes=expire_minutes,
        expire_timedelta=expire_timedelta,
    )


async def encode_jwt(
    payload: dict,
    private_key: str = config.auth_jwt.PRIVATE_KEY_PATH.read_text(),
    algorithm: str = config.auth_jwt.ALGORITHM,
    expire_minutes: int = config.auth_jwt.ACCESS_TOKEN_EXPIRE_MINUTES,
    expire_timedelta: timedelta | None = None,
):
    to_encode = payload.copy()
    now_utc = datetime.now(UTC)
    if expire_timedelta:
        expire = now_utc + expire_timedelta
    else:
        expire = now_utc + timedelta(minutes=expire_minutes)
    to_encode.update(exp=expire, iat=now_utc)

    encoded = await asyncio.to_thread(
        jwt.encode, to_encode, private_key, algorithm=algorithm
    )
    return encoded


async def decode_jwt(
    token: str | bytes,
    public_key: str = config.auth_jwt.PUBLIC_KEY_PATH.read_text(),
    algorithm: str = config.auth_jwt.ALGORITHM,
):
    decoded = await asyncio.to_thread(
        jwt.decode, token, public_key, algorithms=[algorithm]
    )
    return decoded


async def hash_password(password: str) -> bytes:
    salt = bcrypt.gensalt()
    return await asyncio.to_thread(bcrypt.hashpw, password.encode(), salt)


async def validate_password(password: str, hashed_password: bytes) -> bool:
    return await asyncio.to_thread(
        bcrypt.checkpw,
        password.encode(),
        hashed_password,
    )


async def send_email(
    recipient: str, subject: str, plain_content: str, html_content: str = ""
):
    message = MIMEMultipart("alternative")
    message["From"] = config.email.EMAIL_USERNAME
    message["To"] = recipient
    message["Subject"] = subject

    plain_text_message = MIMEText(
        plain_content,
        "plain",
        "utf-8",
    )
    message.attach(plain_text_message)

    if html_content:
        html_message = MIMEText(
            html_content,
            "html",
            "utf-8",
        )
        message.attach(html_message)

    smtp_client = SMTP(
        hostname=config.email.EMAIL_HOST,
        port=config.email.EMAIL_PORT,
        use_tls=True,
    )

    async with smtp_client:
        await smtp_client.login(
            config.email.EMAIL_USERNAME,
            config.email.EMAIL_PASSWORD.get_secret_value(),
        )
        await smtp_client.send_message(message)
