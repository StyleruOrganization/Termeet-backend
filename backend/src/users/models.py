from uuid import uuid4, UUID
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ARRAY

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings, Teams


class Users(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[Optional[str]]
    additional_email: Mapped[Optional[list[str]]] = mapped_column(
        ARRAY(String)
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
