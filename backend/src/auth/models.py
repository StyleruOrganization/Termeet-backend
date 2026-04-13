from uuid import UUID, uuid4
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.users.models import Users


class OAuthEnum(Enum):
    YANDEX = "YANDEX"


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Возможно стоит добавить client_id, который приходит от Яндекса,
    # чтобы потом пользоваться сервисами Яндекса

    provider: Mapped[str] = mapped_column(
        PgEnum(OAuthEnum, name="oauth_enum", create_type=False),
        nullable=False
        )
    provider_user_id: Mapped[int] = mapped_column(nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["Users"] = relationship(back_populates="oauth_accounts")
