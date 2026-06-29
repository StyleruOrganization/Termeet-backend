from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DataRangeGRPC(_message.Message):
    __slots__ = ("time_interval",)
    TIME_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    time_interval: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, time_interval: _Optional[_Iterable[str]] = ...) -> None: ...

class MeetingCreateRequestGRPC(_message.Message):
    __slots__ = ("name", "data_range", "description", "duration", "link")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DATA_RANGE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    LINK_FIELD_NUMBER: _ClassVar[int]
    name: str
    data_range: _containers.RepeatedCompositeFieldContainer[DataRangeGRPC]
    description: str
    duration: str
    link: str
    def __init__(self, name: _Optional[str] = ..., data_range: _Optional[_Iterable[_Union[DataRangeGRPC, _Mapping]]] = ..., description: _Optional[str] = ..., duration: _Optional[str] = ..., link: _Optional[str] = ...) -> None: ...

class MeetingCreateResponseGRPC(_message.Message):
    __slots__ = ("hash",)
    HASH_FIELD_NUMBER: _ClassVar[int]
    hash: str
    def __init__(self, hash: _Optional[str] = ...) -> None: ...
