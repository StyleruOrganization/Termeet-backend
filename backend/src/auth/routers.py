from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from backend.src.auth.schemas import Code, AuthTokens, YandexUserData
from backend.src.auth.services import Service


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
             summary="Отправка кода и получения данных пользователя \
                 из Яндекс аккаунта",
             description="Код отправляется на ручку Яндекса \
                для получения токенов, после уже access токен \
                отправляется на ручку Яндекса, для получения  \
                доступной информации о пользователе"
             )
async def handle_code(
    code: Code
):
    service = Service()
    tokens: AuthTokens = await service.get_yandex_tokens(code)
    user_data: YandexUserData = await service.get_yandex_user_data(
        tokens.access_token
        )
    return user_data
