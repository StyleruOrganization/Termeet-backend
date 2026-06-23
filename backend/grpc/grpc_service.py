import asyncio

import grpc
from grpc import aio
from google.protobuf.empty_pb2 import Empty

from backend.grpc.generated.service_pb2_grpc import (
    FeedbackServicer,
)
from backend.grpc.generated.service_pb2 import FeedbackResponse, FeedbackSchema

GRPC_FEEDBACKS = FeedbackResponse(
    feedbacks=[
        FeedbackSchema(
            type="HELP",
            communication_channel="TELEGRAM",
            contact=f"{i}@d10110101",
            message=str(i),
        )
        for i in range(100000)
    ]
)


class FeedbackService(FeedbackServicer):

    async def GetAllFeedback(
        self, request: Empty, context: aio.ServicerContext
    ) -> FeedbackResponse:

        return GRPC_FEEDBACKS
