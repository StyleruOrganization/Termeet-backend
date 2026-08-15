from datetime import datetime, timedelta, timezone
from textwrap import dedent
from typing import TYPE_CHECKING
from urllib import parse

import httpx
from fastapi import HTTPException, status

from backend.src.jinja_templates import templates
from backend.src.users.schemas import UserSchema
from backend.src.integrations.yandex_telemost import (
    YANDEX_INTEGRATION_SCOPES,
)
from backend.src.users.models import Users
from backend.src.auth.schemas import (
    Code,
    Email,
    Password,
    AuthTokens,
    RegisterUserData,
    YandexUserData,
    UserData,
)
from backend.src.auth.infrastructure import Infrastructure
from backend.src.config import config
from backend.src.auth.utils import (
    create_jwt_token,
    send_email,
    hash_password,
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    VERIFICATION_TOKEN_TYPE,
    RESET_PASSWORD_TOKEN_TYPE,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class Service:
    def __init__(
        self,
        session: AsyncSession = None,
    ):
        self.repository = Infrastructure(session)

    async def generate_yandex_oauth_redirect_url(self, intent: str = "login"):
        query_params = {
            "response_type": "code",
            "client_id": config.yandex_auth.CLIENT_ID,
            "redirect_uri": config.yandex_auth.REDIRECT_URI,
            "scope": YANDEX_INTEGRATION_SCOPES,
            "state": "link" if intent == "link" else "login",
        }
        if intent == "link":
            query_params["force_confirm"] = "yes"

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
            "client_secret": config.yandex_auth.CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=base_url, headers=headers, data=data
            )

            tokens = response.json()

        if "access_token" not in tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Exception from yandex: invalid yandex code",
            )

        tokens = AuthTokens(**tokens)

        return tokens

    async def get_yandex_user_data(self, access_token: str):
        base_url = "https://login.yandex.ru/info"
        headers = {"Authorization": f"OAuth {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url=f"{base_url}", headers=headers)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Exception from yandex: invalid yandex token",
                )
            user_data: dict = response.json()

        try:
            return YandexUserData(**user_data)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Exception from yandex: invalid yandex token",
            )

    async def auth_yandex_user(
        self,
        user_data: YandexUserData,
        tokens: AuthTokens,
        current_user: UserSchema | None = None,
    ) -> UserSchema:
        expires_at = None
        if tokens.expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=tokens.expires_in
            )

        existing = await self.repository.yandex_check_user_in_db(user_data)
        email_user = await self.repository.check_user_in_db_by_email(
            user_data.default_email
        )

        if current_user:
            if existing and str(existing.id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This Yandex account is already linked to another user",
                )
            record = await self.repository.get_user_by_id(current_user.id)
            await self.repository.upsert_yandex_oauth(
                record,
                user_data,
                tokens,
                YANDEX_INTEGRATION_SCOPES,
                expires_at,
            )
            return UserSchema.model_validate(record)

        if existing:
            await self.repository.upsert_yandex_oauth(
                existing,
                user_data,
                tokens,
                YANDEX_INTEGRATION_SCOPES,
                expires_at,
            )
            return UserSchema.model_validate(existing)

        if email_user:
            await self.repository.upsert_yandex_oauth(
                email_user,
                user_data,
                tokens,
                YANDEX_INTEGRATION_SCOPES,
                expires_at,
            )
            return UserSchema.model_validate(email_user)

        created: UserData = UserData.from_yandex(user_data)
        user: Users = await self.repository.register_user(created)
        await self.repository.upsert_yandex_oauth(
            user,
            user_data,
            tokens,
            YANDEX_INTEGRATION_SCOPES,
            expires_at,
        )
        return UserSchema.model_validate(user)

    async def create_tokens(self, user: UserSchema, only_access: bool = False):
        access_token = await self.create_access_token(user)
        refresh_token = None

        if not only_access:
            refresh_token = await self.create_refresh_token(user)

        return access_token, refresh_token

    async def create_access_token(self, user: UserSchema):
        jwt_payload = {
            "sub": str(user.id),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }

        access_token: str = await create_jwt_token(
            token_type=ACCESS_TOKEN_TYPE,
            token_data=jwt_payload,
            expire_minutes=config.auth_jwt.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

        return access_token

    async def create_refresh_token(self, user: UserSchema):
        jwt_payload = {"sub": str(user.id)}

        refresh_token: str = await create_jwt_token(
            token_type=REFRESH_TOKEN_TYPE,
            token_data=jwt_payload,
            expire_timedelta=timedelta(
                days=config.auth_jwt.REFRESH_TOKEN_EXPIRE_DAYS
            ),
        )

        return refresh_token

    async def register_user(self, user_reg_data: RegisterUserData) -> UserSchema:
        if user := (
            await self.repository.check_user_in_db_by_email(user_reg_data.email)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        user_data: UserData = await UserData.from_register(user_reg_data)
        user: Users = await self.repository.register_user(user_data)
        await self.repository.session.commit()
        user: UserSchema = UserSchema.model_validate(user)

        return user

    async def create_verification_token_and_send_email(self, user: UserSchema) -> UserSchema:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You must be authenticated to confirm email",
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already verified",
            )

        jwt_payload = {
            "sub": str(user.id),
        }

        verification_token = await create_jwt_token(
            token_type=VERIFICATION_TOKEN_TYPE,
            token_data=jwt_payload,
            expire_minutes=config.email.VERIFICATION_TOKEN_EXPIRE_MINUTES,
        )

        query_params = {
            "token": verification_token,
        }

        query_string = parse.urlencode(query_params, quote_via=parse.quote)
        verification_link = f"{config.email.VERIFICATION_LINK}?{query_string}"

        await self.send_verification_email(user, verification_link)

    async def set_verify_user(self, user: UserSchema):
        user: Users = await self.repository.set_verify_user(user)

        return {"detail": "User verified successfully"}

    async def create_reset_password_token_and_send_email(self, email: Email):
        recipient = str(email.email).strip().lower()
        user = await self.repository.check_user_in_db_by_email(recipient)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User with this email not found",
            )
        if not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Смена пароля недоступна для аккаунтов, вошедших через Яндекс",
            )

        jwt_payload = {
            "sub": str(user.id),
        }

        reset_password_token = await create_jwt_token(
            token_type=RESET_PASSWORD_TOKEN_TYPE,
            token_data=jwt_payload,
            expire_minutes=(
                config.reset_password.RESET_PASSWORD_TOKEN_EXPIRE_MINUTES
            ),
        )

        query_params = {
            "token": reset_password_token,
        }

        query_string = parse.urlencode(query_params, quote_via=parse.quote)
        reset_password_link = (
            f"{config.reset_password.RESET_PASSWORD_LINK}?{query_string}"
        )

        await self.send_reset_password_email(recipient, reset_password_link)

    async def send_reset_password_email(self, email, reset_password_link):
        recipient = email

        subject = "Сброс пароля"

        plain_content = dedent(f"""\
            Здравствуйте, для сброса пароля перейдите по ссылке:
            {reset_password_link}

            Ваш администратор сайта Termeet,
            © 2026.
            """)

        template = templates.get_template("reset_password_email.html")

        html_content = template.render(reset_password_link=reset_password_link)

        await send_email(
            recipient=recipient,
            subject=subject,
            plain_content=plain_content,
            html_content=html_content,
        )

    async def set_new_password(self, user: UserSchema, password: Password):
        db_user = await self.repository.get_user_by_id(user.id)
        if not db_user or not db_user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Смена пароля недоступна для аккаунтов, вошедших через Яндекс",
            )
        password_value = password.password
        password_hash = await hash_password(password_value)
        await self.repository.set_new_password(user, password_hash)

        return user


    async def send_verification_email(
        self,
        user: UserData,
        verification_link: str,
    ):
        recipient = user.email

        subject = "Подтверждение регистрации"

        plain_content = dedent(f"""\
            Здравствуйте, {user.last_name} {user.first_name} \
                для подтверждения регистрации перейдите по ссылке:
            {verification_link}

            Ваш администратор сайта Termeet,
            © 2026.
            """)

        template = templates.get_template("verification_email.html")

        html_content = template.render(
            verification_link=verification_link,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        await send_email(
            recipient=recipient,
            subject=subject,
            plain_content=plain_content,
            html_content=html_content,
        )
