from uuid import uuid4, UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ARRAY

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings
    from backend.src.teams.models import Teams
    from backend.src.auth.models import OAuthAccount


class Users(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    email: Mapped[Optional[str]]
    additional_emails: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String)
        )

    oauth_accounts: Mapped[Optional[list["OAuthAccount"]]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    meetings_owner: Mapped[Optional[list["Meetings"]]] = relationship(
        back_populates="owner"
    )
    meetings_participant: Mapped[
        Optional[list["Meetings"]]
        ] = relationship(
            back_populates="participants",
            secondary="meetings_users"
            )

    teams: Mapped[Optional[list["Teams"]]] = relationship(
        back_populates="user"
    )
