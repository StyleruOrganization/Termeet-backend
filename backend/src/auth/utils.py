import asyncio
from datetime import timedelta, datetime, UTC
from fastapi import HTTPException, status

import jwt
import bcrypt
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.src.config import config

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

    send_email_args = {
        "hostname": config.email.EMAIL_HOST,
        "port": config.email.EMAIL_PORT,
    }

    if not config.email.USE_MAILDEV:
        send_email_args["username"] = config.email.EMAIL_USERNAME
        send_email_args["password"] = config.email.EMAIL_PASSWORD.get_secret_value()
        send_email_args["use_tls"] = True

    try:
        await aiosmtplib.send(message, **send_email_args)
    except Exception as e:
        # Придумать, как обрабатывать эти ошибки по-другому
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    # try:
    #     # Для Яндекса обычно используется порт 465 и use_tls=True
    #     await aiosmtplib.send(
    #         message,
    #         hostname="smtp.yandex.ru",
    #         port=465,
    #         username="your-login@yandex.ru",
    #         password="your-app-password", # Используйте ПАРОЛЬ ПРИЛОЖЕНИЯ, а не личный
    #         use_tls=True,
    #     )
    #     print("Письмо успешно отправлено на сервер!")

    # except aiosmtplib.SMTPRecipientRefused:
    #     # Самая важная для вас ошибка: сервер получателя сразу сказал, что адреса не существует
    #     print(f"Ошибка: Адрес {recipient_email} отклонен сервером (не существует).")

    # except aiosmtplib.SMTPAuthenticationError:
    #     # Ошибка логина/пароля или не включен SMTP в настройках Яндекса
    #     print("Ошибка: Не удалось войти. Проверьте логин и пароль приложения.")

    # except aiosmtplib.SMTPDataError:
    #     # Яндекс часто кидает эту ошибку, если посчитал ваше письмо спамом
    #     print("Ошибка: Письмо отклонено сервером Яндекса (возможно, спам).")

    # except aiosmtplib.SMTPConnectError:
    #     print("Ошибка: Не удалось подключиться к серверу Яндекса.")

    # except aiosmtplib.SMTPException as e:
    #     # Базовое исключение для всех остальных ошибок SMTP
    #     print(f"Произошла общая ошибка SMTP: {e}")

    # except Exception as e:
    #     # Ошибки сети, таймауты и прочее
    #     print(f"Системная ошибка: {e}")
