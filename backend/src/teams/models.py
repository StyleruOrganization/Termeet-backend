from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import ARRAY, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings
    from backend.src.users.models import Users


class TeamsUsers(Base):
    __tablename__ = "teams_users"

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class Teams(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(
        String(400), nullable=False, default="", server_default=""
    )
    emails: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))
    photo_key: Mapped[Optional[str]] = mapped_column(String(256))

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    user: Mapped["Users"] = relationship(back_populates="teams")

    members: Mapped[list["Users"]] = relationship(
        secondary="teams_users",
        back_populates="member_teams",
    )

    meetings: Mapped[Optional[list["Meetings"]]] = relationship(
        back_populates="team"
    )
