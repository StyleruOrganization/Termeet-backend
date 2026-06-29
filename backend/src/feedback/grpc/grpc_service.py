from typing import TYPE_CHECKING

from grpc import aio
from google.protobuf.empty_pb2 import Empty

from backend.src.feedback.grpc.generated.service_pb2_grpc import (
    FeedbackGRPCServicer,
)
from backend.src.feedback.grpc.generated.service_pb2 import (
    FeedbackResponseGRPC,
    FeedbackSchemaGRPC,
    FeedbackTypeGRPC,
    CommunicationChannelGRPC,
)

from backend.src.feedback.infrastructures import Infrastructure

if TYPE_CHECKING:
    from backend.src.feedback.models import Feedback


class FeedbackService(FeedbackGRPCServicer):
    def __init__(
        self,
        session_factory=None,
    ):
        self.session_factory = session_factory

    async def GetAllFeedback(
        self, request: Empty, context: aio.ServicerContext
    ) -> FeedbackResponseGRPC:

        async with self.session_factory() as session:
            async with session.begin():
                repository = Infrastructure(session)

                feedbacks: list["Feedback"] = (
                    await repository.get_all_feedbacks()
                )

        feedback: FeedbackResponseGRPC = FeedbackResponseGRPC(
            feedbacks=[
                FeedbackSchemaGRPC(
                    type=FeedbackTypeGRPC.Value(f.type),
                    communication_channel=CommunicationChannelGRPC.Value(
                        f.communication_channel
                    ),
                    contact=f.contact,
                    message=f.message,
                )
                for f in feedbacks
            ]
        )

        return feedback
