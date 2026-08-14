from uuid import uuid4, UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, Computed, LargeBinary, String, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings
    from backend.src.teams.models import Teams
    from backend.src.auth.models import OAuthAccount
    from backend.src.feedback.models import Feedback


class Users(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(
        String(50), Computed("first_name"))
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    email: Mapped[Optional[str]] = mapped_column(unique=True, index=True)
    additional_emails: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String)
    )

    password_hash: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary(), nullable=True
    )

    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UTC +3:00 (Москва)",
        server_default="UTC +3:00 (Москва)",
    )
    theme: Mapped[str] = mapped_column(
        String(16), nullable=False, default="light", server_default="light"
    )
    suggest_prefill: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    availability_template: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=lambda: [], server_default="[]"
    )

    oauth_accounts: Mapped[Optional[list["OAuthAccount"]]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    meetings_owner: Mapped[Optional[list["Meetings"]]] = relationship(
        back_populates="owner"
    )
    meetings_participant: Mapped[Optional[list["Meetings"]]] = relationship(
        back_populates="participants", secondary="meetings_users"
    )

    feedbacks: Mapped[Optional["Feedback"]] = relationship(back_populates="user")

    teams: Mapped[Optional[list["Teams"]]] = relationship(
        back_populates="user"
    )
