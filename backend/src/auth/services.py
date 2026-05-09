from textwrap import dedent
from typing import TYPE_CHECKING
from urllib import parse
from datetime import timedelta

import httpx
from fastapi import HTTPException, status

from backend.src.jinja_templates import templates
from backend.src.users.schemas import UserSchema
from backend.src.auth.infrastructure import Infrastructure
from backend.src.auth.schemas import (
    Code,
    Email,
    Password,
    AuthTokens,
    RegisterUserData,
    YandexUserData,
    UserData,
)
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
    from fastapi import BackgroundTasks
    from backend.src.users.models import Users


class Service:
    def __init__(
        self,
        session: AsyncSession = None,
        background_tasks: BackgroundTasks = None,
    ):
        self.repository = Infrastructure(session)
        self.background_tasks = background_tasks

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

            user_data: dict = response.json()

        user_data = YandexUserData(**user_data)

        return user_data

    async def auth_yandex_user(self, user_data: YandexUserData) -> UserSchema:

        if user := (await self.repository.yandex_check_user_in_db(user_data)):
            user: UserSchema = UserSchema.model_validate(user)
            return user

        if user := (
            await self.repository.check_user_in_db_by_email(
                user_data.default_email
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        user_data: UserData = UserData.from_yandex(user_data)
        user: Users = await self.repository.register_user(user_data)
        user: UserSchema = UserSchema.model_validate(user)
        return user

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
        user: UserSchema = UserSchema.model_validate(user)

        if user_reg_data.do_verify_email:
            await self.create_verification_token_and_send_email(user)

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

        self.background_tasks.add_task(self.send_verification_email, user, verification_link)

    async def set_verify_user(self, user: UserSchema):
        user: Users = await self.repository.set_verify_user(user)

        return {"detail": "User verified successfully"}

    async def create_reset_password_token_and_send_email(self, email: Email):
        email = email.email
        if user := (await self.repository.check_user_in_db_by_email(email)):

            jwt_payload = {
                "sub": str(user.id),
            }

            reset_password_token = await create_jwt_token(
                token_type=RESET_PASSWORD_TOKEN_TYPE,
                token_data=jwt_payload,
                expire_minutes=config.reset_password.RESET_PASSWORD_TOKEN_EXPIRE_MINUTES,
            )

            query_params = {
                "token": reset_password_token,
            }

            query_string = parse.urlencode(query_params, quote_via=parse.quote)
            reset_password_link = f"{config.reset_password.RESET_PASSWORD_LINK}?{query_string}"

            self.background_tasks.add_task(self.send_reset_password_email, email, reset_password_link)

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

        return await send_email(
            recipient=recipient,
            subject=subject,
            plain_content=plain_content,
            html_content=html_content,
        )

    async def set_new_password(self, user: UserSchema, password: Password):
        password = password.password
        password_hash = await hash_password(password)
        await self.repository.set_new_password(user, password_hash)

        return {"detail": "The new password was set successfully"}


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

        return await send_email(
            recipient=recipient,
            subject=subject,
            plain_content=plain_content,
            html_content=html_content,
        )
