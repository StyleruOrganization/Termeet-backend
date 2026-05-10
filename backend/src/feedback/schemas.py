from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from fastapi import Form


class FeedbackType(str, Enum):
    HELP = "HELP"
    SUGGESTION = "SUGGESTION"
    BUG = "BUG"
    PARTNERSHIP = "PARTNERSHIP"
    OTHER = "OTHER"


class CommunicationChannel(str, Enum):
    EMAIL = "EMAIL"
    TELEGRAM = "TELEGRAM"


class Feedback(BaseModel):
    id: UUID | None = None
    type: FeedbackType
    communication_channel: CommunicationChannel
    contact: str
    message: str

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
