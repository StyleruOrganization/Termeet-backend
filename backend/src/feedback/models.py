from typing import TYPE_CHECKING, Optional
from uuid import uuid4, UUID
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy import ForeignKey

from backend.src.models import Base
from backend.src.feedback.schemas import FeedbackType, CommunicationChannel

if TYPE_CHECKING:
    from backend.src.users.models import Users


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[FeedbackType] = mapped_column(
        PgEnum(FeedbackType, name="feedback_type", create_type=False),
        nullable=False,
    )
    communication_channel = mapped_column(
        PgEnum(
            CommunicationChannel,
            name="communication_channel",
            create_type=False,
        ),
        nullable=False,
    )
    contact: Mapped[str] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)

    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    user: Mapped[Optional["Users"]] = relationship(back_populates="feedbacks")
