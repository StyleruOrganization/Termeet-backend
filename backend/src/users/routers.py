from fastapi import APIRouter, Depends

from backend.src.auth.dependencies import get_current_active_user
from backend.src.users.schemas import UserSchema


router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    summary="Информация о текущем пользователе",
    description="Получает юзера из access-токена, проверяет его в БД и \
        возвращает его данные",
)
async def auth_user(user: UserSchema = Depends(get_current_active_user)):
    return user
