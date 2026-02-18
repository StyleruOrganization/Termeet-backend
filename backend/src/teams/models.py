from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ARRAY, String, ForeignKey

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings
    from backend.src.users.models import Users


class Teams(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str]
    emails: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["Users"] = relationship(back_populates="teams")

    meetings: Mapped[Optional[list["Meetings"]]] = relationship(
        back_populates="team"
    )
