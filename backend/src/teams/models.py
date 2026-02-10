from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ARRAY, String

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings


class Teams(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    emails: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    meetings: Mapped[list["Meetings"]] = relationship(
        "Meetings", back_populates="team"
    )
