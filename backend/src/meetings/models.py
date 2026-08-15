from datetime import datetime
from uuid import uuid4, UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, DateTime, String, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql.json import JSONB

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.users.models import Users
    from backend.src.teams.models import Teams


class Meetings(Base):
    __tablename__ = "meetings"

    def __str__(self):
        # Допиши этот метод
        return (
            f"MEETING <"
            f"ID {self.id} "
            f"NAME {self.name} "
            f"DESCRIPTION {self.description} "
            f"LINK {self.link} "
            f"DURATION {self.duration} "
            f"DATA_RANGE {self.data_range} "
            f"SLOTS {self.slots} "
            f"EMAILS {self.emails}>"
            f"OWNER_ID {self.owner_id} "
            f"TEAM_ID {self.team_id}>"
        )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    link: Mapped[Optional[str]] = mapped_column(String(256))
    duration: Mapped[Optional[str]]

    data_range: Mapped[list[list[str]]] = mapped_column(JSONB, nullable=False)

    slots: Mapped[Optional[list]] = mapped_column(
        JSONB, default=lambda: [], server_default="[]"
    )

    emails: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))

    anyone_can_edit: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    anyone_can_delete_participants: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    require_login_to_vote: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    anyone_can_set_final: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    final_slot: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    invited_user_ids: Mapped[list] = mapped_column(
        JSONB, default=lambda: [], server_default="[]", nullable=False
    )
    observers: Mapped[list] = mapped_column(
        JSONB, default=lambda: [], server_default="[]", nullable=False
    )
    calendar_events: Mapped[dict] = mapped_column(
        JSONB, default=lambda: {}, server_default="{}", nullable=False
    )
    is_closed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    invite_only_vote: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    vote_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    remind_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    remind_offsets: Mapped[list] = mapped_column(
        JSONB, default=lambda: [], server_default="[]", nullable=False
    )
    remind_sent: Mapped[list] = mapped_column(
        JSONB, default=lambda: [], server_default="[]", nullable=False
    )
    lock_vote_after_deadline: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # Поля, обязательные для залогинов
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    owner: Mapped[Optional["Users"]] = relationship(
        back_populates="meetings_owner"
    )

    participants: Mapped[Optional[list["Users"]]] = relationship(
        back_populates="meetings_participant", secondary="meetings_users"
    )

    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("teams.id"), nullable=True
    )
    team: Mapped[Optional["Teams"]] = relationship(back_populates="meetings")


class MeetingsUsers(Base):
    __tablename__ = "meetings_users"

    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
