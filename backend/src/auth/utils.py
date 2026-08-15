import asyncio
import logging
from datetime import timedelta, datetime, UTC
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import jwt
import bcrypt
import aiosmtplib
from fastapi import HTTPException

from backend.src.config import config

logger = logging.getLogger(__name__)

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
VERIFICATION_TOKEN_TYPE = "verification"
RESET_PASSWORD_TOKEN_TYPE = "reset_password"
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


def _hash_as_bytes(hashed_password: bytes | str | memoryview) -> bytes:
    if isinstance(hashed_password, memoryview):
        hashed_password = hashed_password.tobytes()
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode("utf-8")
    return bytes(hashed_password).rstrip(b"\x00")


async def hash_password(password: str) -> bytes:
    salt = bcrypt.gensalt()
    return await asyncio.to_thread(
        bcrypt.hashpw, password.encode("utf-8"), salt
    )


async def validate_password(
    password: str, hashed_password: bytes | str | memoryview
) -> bool:
    try:
        return await asyncio.to_thread(
            bcrypt.checkpw,
            password.encode("utf-8"),
            _hash_as_bytes(hashed_password),
        )
    except (TypeError, ValueError):
        return False


async def send_email(
    recipient: str,
    subject: str,
    plain_content: str,
    html_content: str = "",
    ics_content: str | None = None,
):
    mailbox = (config.email.EMAIL_USERNAME or "").strip()
    sender = mailbox or "noreply@termeet.tech"
    message = EmailMessage()
    message["From"] = formataddr(("Termeet", sender))
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain="termeet.tech")
    message.set_content(plain_content)
    if html_content:
        message.add_alternative(html_content, subtype="html")
    if ics_content:
        message.add_attachment(
            ics_content.encode("utf-8"),
            maintype="text",
            subtype="calendar",
            filename="termeet.ics",
        )

    send_email_args = {
        "hostname": config.email.EMAIL_HOST,
        "port": config.email.EMAIL_PORT,
        "timeout": 30,
        "sender": sender,
    }

    if config.email.USE_MAILDEV:
        send_email_args["use_tls"] = False
        send_email_args["start_tls"] = False
    else:
        password = (
            config.email.EMAIL_PASSWORD.get_secret_value()
            if config.email.EMAIL_PASSWORD
            else ""
        )
        if not mailbox or not password:
            logger.error(
                "Email credentials are missing, cannot send to %s", recipient
            )
            raise HTTPException(
                status_code=503,
                detail="Failed to send email",
            )
        send_email_args["username"] = mailbox
        send_email_args["password"] = password
        # Яндекс: 465 — SSL сразу, 587 — сначала без шифрования, потом STARTTLS.
        if config.email.EMAIL_PORT == 587:
            send_email_args["use_tls"] = False
            send_email_args["start_tls"] = True
        else:
            send_email_args["use_tls"] = True
            send_email_args["start_tls"] = False

    try:
        await aiosmtplib.send(message, **send_email_args)
        logger.info("Email sent to %s (%s)", recipient, subject)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to send email to %s", recipient)
        raise HTTPException(
            status_code=503,
            detail="Failed to send email",
        ) from None
