from fastapi import Form
from backend.src.feedback.schemas import (
    Feedback,
    FeedbackType,
    CommunicationChannel,
)


def feedback_as_form(
    type: FeedbackType = Form(...),
    communication_channel: CommunicationChannel = Form(...),
    contact: str = Form(...),
    message: str = Form(...),
) -> Feedback:
    return Feedback(
        type=type,
        communication_channel=communication_channel,
        contact=contact,
        message=message,
    )
