from fastapi import APIRouter, Depends, Form, Response, BackgroundTasks
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.schemas import ErrorResponse
from backend.src.dependencies import get_async_session
from backend.src.users.schemas import UserSchema
from backend.src.auth.schemas import (
    Code,
    Email,
    Password,
    AuthTokens,
    RegisterUserData,
    YandexUserData,
    TokenInfo,
)
from backend.src.auth.services import Service
from backend.src.auth.dependencies import (
    get_current_active_user,
    get_current_auth_user_from_validation,
    get_current_auth_user_from_refresh,
    get_current_auth_user_from_reset_password,
    validate_login_user,
)
from backend.src.auth.utils import REFRESH_TOKEN_COOKIE
from backend.src.config import config

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/yandex/url",
    summary="Перенаправить на страницу авторизации Яндекса",
    description="Получает специальный код через редирект на  \
                фронтенд, с помощью которого потом можно получить в \
                access и refresh токены от Яндекса",
)
async def get_yandex_oauth_url():
    service = Service()
    url = await service.generate_yandex_oauth_redirect_url()
    return RedirectResponse(url=url, status_code=302)


@router.post(
    "/yandex/callback",
    summary="Отправка кода, получения данных пользователя, \
                 выдача токенов",
    description="Код отправляется на ручку Яндекса \
                для получения токенов, после уже access токен \
                отправляется на ручку Яндекса, для получения  \
                доступной информации о пользователе, дальше идет \
                запись в БД, выдача токенов, которые отсылаются \
                в куках (refresh) и в Authorization: Bearer (access)",
    response_model=TokenInfo,
    responses={
        401: {
            "description": "Не валидный code от Яндекса",
            "model": ErrorResponse,
        },
        400: {
            "description": "Пользователь с эти email-ом уже существует",
            "model": ErrorResponse,
        },
    },
)
async def auth_yandex_issue_jwt(
    response: Response,
    code: Code,
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session)

    tokens: AuthTokens = await service.get_yandex_tokens(code)
    user_data: YandexUserData = await service.get_yandex_user_data(
        tokens.access_token
    )

    user: UserSchema = await service.auth_yandex_user(user_data)
    await service.set_verify_user(user)

    access_token, refresh_token = await service.create_tokens(user)

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        path="/",
        httponly=True,
        secure=config.cookies.HTTPS_TRUE,
        samesite="lax",
    )

    return TokenInfo(access_token=access_token)


@router.post(
    "/refresh",
    summary="Обновить access токен",
    description="Обновляется access токен по refresh токену",
    response_model=TokenInfo,
    responses={
        401: {
            "description": "Срок действия refresh-токена истек \
                Не правильный тип токена",
            "model": ErrorResponse,
        },
    },
)
async def auth_refresh_jwt(
    user: UserSchema = Depends(get_current_auth_user_from_refresh),
):
    service = Service()

    access_token, _ = await service.create_tokens(user, only_access=True)

    return TokenInfo(access_token=access_token)


@router.post(
    "/confirm-email/verify",
    summary="Проверка токена верификации почты",
    description="Проверяет валидность токена верификации почты",
    responses={
        401: {
            "description": "Срок действия токена истек \
                Не правильный тип токена",
            "model": ErrorResponse,
        },
    },
)
async def verify_token(
    user: UserSchema = Depends(get_current_auth_user_from_validation),
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session)
    return await service.set_verify_user(user)


@router.post(
    "/confirm-email",
    summary="Подтверждение email",
    description="Подтверждает email, отправляет письмо с подтверждением",
)
async def confirm_email(
    background_tasks: BackgroundTasks,
    user: UserSchema = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session, background_tasks)
    await service.create_verification_token_and_send_email(user)

    return {"detail": "Email sent successfully"}


@router.post(
    "/reset-password",
    summary="Сброс пароля",
    description="Подтверждает email, отправляет письмо с подтверждением, \
                 отправляет письмо с ссылкой для сброса пароля",
)
async def reset_password(
    background_tasks: BackgroundTasks,
    email: Email,
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session, background_tasks)
    await service.create_reset_password_token_and_send_email(email)

    return {"detail": "Email sent successfully"}


@router.post(
    "/reset-password/verify",
    summary="Проверка токена сброса пароля и замена пароля на новый",
    description="Проверяет валидность токена сброса пароля",
    responses={
        401: {
            "description": "Срок действия токена истек \
                Не правильный тип токена",
            "model": ErrorResponse,
        },
        404: {
            "description": "Объект не найден",
            "model": ErrorResponse,
        },
    },
)
async def verify_reset_password_token(
    password: Password,
    user: UserSchema = Depends(get_current_auth_user_from_reset_password),
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session)
    return await service.set_new_password(user, password)

@router.post(
    "/register",
    summary="Регистрация нового пользователя",
    description="Регистрирует нового пользователя, получает его данные, \
                 хеширует пароль, сохраняет в БД; также отправляет \
                 письмо с подтверждением",
    response_model=UserSchema,
    responses={
        400: {
            "description": "Пользователь с эти email-ом уже существует",
            "model": ErrorResponse,
        },
    },
)
async def default_register_user(
    background_tasks: BackgroundTasks,
    user_data: RegisterUserData,
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session, background_tasks)
    # Метод сервиса снизу включает верификацию
    user = await service.register_user(user_data)
    return user


@router.post(
    "/login",
    summary="Авторизация пользователя, выдача токенов",
    description="Авторизует пользователя по email и паролю, \
        выдаёт access и refresh токен",
    response_model=TokenInfo,
    responses={
        401: {
            "description": "Не верный логин или пароль",
            "model": ErrorResponse,
        },
        403: {
            "description": "Пользователь заблокирован",
            "model": ErrorResponse,
        },
    },
)
async def auth_user_issue_jwt(
    response: Response,
    user: UserSchema = Depends(validate_login_user),
    session: AsyncSession = Depends(get_async_session),
):
    service = Service(session)
    access_token, refresh_token = await service.create_tokens(user)

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        path="/",
        httponly=True,
        secure=config.cookies.HTTPS_TRUE,
        samesite="lax",
    )

    return TokenInfo(access_token=access_token)


@router.post(
    "/logout",
    summary="Выход пользователя из системы",
    description="Удаляет refresh токен из куки, тем самым \
                 разлогинивая пользователя. Access токен \
                 удаляется на клиенте",
)
async def logout_user(response: Response):
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path="/",
    )
    return {"detail": "Successfully logged out"}
