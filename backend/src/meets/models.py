from datetime import time, date
import uuid

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Time, ARRAY, Date


class Base(DeclarativeBase):
    pass


class Meetings(Base):
    __tablename__ = "meetings"

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
    # duration: Mapped[] = mapped_column()  # Поле продолжительность
    # Поле - внешний ключ на команду
    emails: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    # Добавить проверку на правильность введенного поля
