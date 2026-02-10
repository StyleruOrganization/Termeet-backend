from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ARRAY

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings, MeetingsUsers


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)  # Возможно стоит uuid
    name: Mapped[str] = mapped_column(String(50))
    surname: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column()  # Добавить проверку валидности
    additional_email: Mapped[list[str] | None] = mapped_column(ARRAY(str))
    # Возможно стоит добавить что-то типо подключенных календарей
    meetings_owner: Mapped[list["Meetings"]] = relationship(
        "Meetings", back_populates="owner"
    )
    meetings_participant: Mapped[list["MeetingsUsers"]] = relationship(
        "MeetingsUsers", back_populates="user"
    )
