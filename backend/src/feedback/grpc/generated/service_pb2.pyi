from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import (
    ClassVar as _ClassVar,
    Optional as _Optional,
    Union as _Union,
)

DESCRIPTOR: _descriptor.FileDescriptor

class FeedbackTypeGRPC(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    HELP: _ClassVar[FeedbackTypeGRPC]
    SUGGESTION: _ClassVar[FeedbackTypeGRPC]
    BUG: _ClassVar[FeedbackTypeGRPC]
    PARTNERSHIP: _ClassVar[FeedbackTypeGRPC]
    OTHER: _ClassVar[FeedbackTypeGRPC]

class CommunicationChannelGRPC(
    int, metaclass=_enum_type_wrapper.EnumTypeWrapper
):
    __slots__ = ()
    EMAIL: _ClassVar[CommunicationChannelGRPC]
    TELEGRAM: _ClassVar[CommunicationChannelGRPC]

HELP: FeedbackTypeGRPC
SUGGESTION: FeedbackTypeGRPC
BUG: FeedbackTypeGRPC
PARTNERSHIP: FeedbackTypeGRPC
OTHER: FeedbackTypeGRPC
EMAIL: CommunicationChannelGRPC
TELEGRAM: CommunicationChannelGRPC

class FeedbackSchemaGRPC(_message.Message):
    __slots__ = ("type", "communication_channel", "contact", "message")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    COMMUNICATION_CHANNEL_FIELD_NUMBER: _ClassVar[int]
    CONTACT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    type: FeedbackTypeGRPC
    communication_channel: CommunicationChannelGRPC
    contact: str
    message: str
    def __init__(
        self,
        type: _Optional[_Union[FeedbackTypeGRPC, str]] = ...,
        communication_channel: _Optional[
            _Union[CommunicationChannelGRPC, str]
        ] = ...,
        contact: _Optional[str] = ...,
        message: _Optional[str] = ...,
    ) -> None: ...

class FeedbackResponseGRPC(_message.Message):
    __slots__ = ("feedbacks",)
    FEEDBACKS_FIELD_NUMBER: _ClassVar[int]
    feedbacks: _containers.RepeatedCompositeFieldContainer[FeedbackSchemaGRPC]
    def __init__(
        self,
        feedbacks: _Optional[
            _Iterable[_Union[FeedbackSchemaGRPC, _Mapping]]
        ] = ...,
    ) -> None: ...
