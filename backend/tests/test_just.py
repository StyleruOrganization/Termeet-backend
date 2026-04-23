import pytest

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.src.users.models import Users
from backend.src.auth.models import OAuthAccount
from backend.src.auth.schemas import UserSchema
from backend.src.dependencies import async_session_maker


def test_config():
    from backend.src.config import BASE_DIR

    print(BASE_DIR)


# @pytest.mark.asyncio
# async def test_register_user(
#     session: AsyncSession = async_session_maker(),
#     user: dict = {
#         "id": "1042247364",
#         "login": "maklakov.daniils",
#         "client_id": "2421c75bbd80418ca1dacae9595c3a54",
#         "display_name": "maklakov.daniils",
#         "real_name": "Даниил Маклаков",
#         "first_name": "Даниил",
#         "last_name": "Маклаков",
#         "sex": "male",
#         "default_email": "daniil@yandex.ru",
#         "emails": ["maklakov.daniils@yandex.ru"],
#         "psuid": "1.AA_lbA.J5jcnC1xk6YXXjGyvh0dQA.nFm8MEKh81UCI0HLpkpseQ",
#     },
# ):
#     query = (
#         select(Users, OAuthAccount)
#         .join(Users.oauth_accounts)
#         .where(OAuthAccount.provider_user_id == int(user["id"]))
#     )
#     result = await session.execute(query)
#     if user := (result.scalar_one_or_none()):
#         user: UserSchema = UserSchema.model_validate(user)
#         print(user)

#     # object = Users(
#     #     first_name=user["first_name"],
#     #     last_name=user["last_name"],
#     #     email=user["default_email"],
#     #     additional_emails=user["emails"]
#     # )
#     # object.oauth_accounts.append(
#     #     OAuthAccount(
#     #         provider="YANDEX",
#     #         provider_user_id=int(user["id"])
#     #     )
#     # )

#     # session.add(object)
#     # await session.flush()
#     # await session.rollback()
#     # await session.commit()


# @pytest.mark.asyncio
# async def test_delete_user(
#         user_id: UUID = UUID("839a0f05-cd38-4a17-8a54-c3cd7ebe2004"),
#         session: AsyncSession = async_session_maker()
#         ):
#     user = await session.get(Users, user_id)
#     await session.delete(user)
#     await session.commit()
