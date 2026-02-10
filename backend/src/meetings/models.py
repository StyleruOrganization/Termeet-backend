import uuid
from datetime import time, date
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Time, ARRAY, Date, ForeignKey

from backend.src.models import Base

if TYPE_CHECKING:
    from backend.src.user.models import Users
    from backend.src.teams.models import Teams


class Meetings(Base):
    __tablename__ = "meetings"

    # Пока по id и будет работать ссылка на встречу
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)  # Есть ли ограничение
    # на размер?
    description: Mapped[str] = mapped_column()
    link: Mapped[str] = mapped_column()  # Не совсем понятно, что за поле
    days: Mapped[list[date] | None] = mapped_column(
        ARRAY(Date), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration: Mapped[int] = mapped_column()  # Поле продолжительность 
    # (какой тип данных)
    emails: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    # Добавить проверку на правильность введенного поля
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["Users"] = relationship(
        "Users", back_populates="meetings_owner"
    )

    participants: Mapped[list["MeetingsUsers"]] = relationship(
        "MeetingsUsers", back_populates="meeting"
    )

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    team: Mapped["Teams"] = relationship("Teams", back_populates="meetings")
    # Здесь явно потом надо обсудить стратегию загрузки моделейв


class MeetingsUsers(Base):
    __tablename__ = "meetings_users"

    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )

    meeting: Mapped["Meetings"] = relationship(
        "Meetings", back_populates="participants"
    )
    user: Mapped["Users"] = relationship(
        "Users", back_populates="meetings_participant"
    )
