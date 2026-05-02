from fastapi import APIRouter, Depends

from backend.src.schemas import ErrorResponse
from backend.src.auth.dependencies import get_current_active_user
from backend.src.users.schemas import UserSchema


router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    summary="Информация о текущем пользователе",
    description="Получает юзера из access-токена, проверяет его в БД и \
        возвращает его данные",
    responses={
        403: {
            "description": "Пользователь заблокирован",
            "model": ErrorResponse
        },
        401: {
            "description": "Срок действия access_токена истек / \
                Не правильный тип токена",
            "model": ErrorResponse
        },
        404: {
            "description": "Объект не найден",
            "model": ErrorResponse
        },
    }
)
async def auth_user(user: UserSchema = Depends(get_current_active_user)):
    return user
