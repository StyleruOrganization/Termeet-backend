from fastapi import APIRouter, Depends, Response
from fastapi.responses import RedirectResponse

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.dependencies import get_async_session
from backend.src.auth.schemas import (
    Code, AuthTokens, YandexUserData, UserSchema, TokenInfo
)
from backend.src.auth.services import Service
from backend.src.auth.dependencies import (
    get_current_active_user,
    get_current_auth_user_for_refresh
)
from backend.src.auth.utils import (
    REFRESH_TOKEN_COOKIE
)
from backend.src.config import config


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/yandex/url",
            summary="Перенаправить на страницу авторизации Яндекса",
            description="Получает специальный код через редирект на  \
                фронтенд, с помощью которого потом можно получитьв \
                access и refresh токены от Яндекса"
            )
async def get_yandex_oauth_url():
    service = Service()
    url = await service.generate_yandex_oauth_redirect_url()
    return RedirectResponse(url=url, status_code=302)


@router.post("/yandex/callback",
             summary="Отправка кода, получения данных пользователя, \
                 выдача токенов",
             description="Код отправляется на ручку Яндекса \
                для получения токенов, после уже access токен \
                отправляется на ручку Яндекса, для получения  \
                доступной информации о пользователе, дальше идет \
                запись в БД, выдача токенов, которые отсылаются \
                в куках (refresh) и в Authorization: Bearer (access)",
             response_model=TokenInfo
             )
async def handle_code(
    response: Response,
    code: Code,
    session: AsyncSession = Depends(get_async_session)
):
    service = Service(session)

    tokens: AuthTokens = await service.get_yandex_tokens(code)
    user_data: YandexUserData = await service.get_yandex_user_data(
        tokens.access_token
        )

    user: UserSchema = await service.authentication_user(user_data)
    access_token, refresh_token = await service.create_tokens(user)

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        path="/",
        httponly=True,
        secure=config.cookies.HTTPS_TRUE,
        samesite="lax"
    )

    return TokenInfo(
        access_token=access_token
    )


@router.post(
        "/yandex/refresh",
        summary="Обновить access токен",
        description="Обновляется access токен по refresh-у",
        response_model=TokenInfo
)
async def auth_refresh_jwt(
    user: UserSchema = Depends(get_current_auth_user_for_refresh),
):
    service = Service()

    access_token, _ = await service.create_tokens(
        user, only_access=True
    )

    return TokenInfo(
        access_token=access_token
    )


@router.get("/users/me")
async def auth_user(
    user: UserSchema = Depends(get_current_active_user)
):
    return user
