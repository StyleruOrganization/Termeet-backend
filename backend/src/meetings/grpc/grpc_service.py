from typing import TYPE_CHECKING

from grpc import aio
from google.protobuf.empty_pb2 import Empty

from backend.src.meetings.grpc.generated.meeting_create_pb2_grpc import (
    MeetingCreateGRPCServicer,
)
from backend.src.meetings.grpc.generated.meeting_create_pb2 import (
    MeetingCreateRequestGRPC,
    MeetingCreateResponseGRPC,
)

from backend.src.meetings.schemas import MeetCreate
from backend.src.meetings.infrastructure import Infrastructure

if TYPE_CHECKING:
    from backend.src.meetings.models import Meetings


class MeetingCreateService(MeetingCreateGRPCServicer):
    def __init__(
        self,
        session_factory=None,
    ):
        self.session_factory = session_factory

    async def create_meeting(
        self, request: MeetingCreateRequestGRPC, context: aio.ServicerContext
    ) -> MeetingCreateResponseGRPC:

        data_range = [
            list(slot.time_interval)
            for slot in request.data_range
        ]

        meeting: MeetCreate = MeetCreate(
            name=request.name,
            description=request.description,
            link=request.link,
            duration=request.duration,
            dataRange=data_range,
        )

        async with self.session_factory() as session:
            async with session.begin():
                repository = Infrastructure(session)

                meeting: Meetings = await repository.create_meeting(meeting)

        return MeetingCreateResponseGRPC(hash=str(meeting.id))
