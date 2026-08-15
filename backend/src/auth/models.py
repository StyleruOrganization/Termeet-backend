from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
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
        PgEnum(OAuthEnum, name="oauth_enum", create_type=False), nullable=False
    )
    provider_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["Users"] = relationship(back_populates="oauth_accounts")
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scopes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    yandex_login: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    yandex_email: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )
