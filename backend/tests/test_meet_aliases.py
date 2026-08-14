from types import SimpleNamespace
from uuid import uuid4

from backend.src.meetings.models import Meetings
from backend.src.meetings.schemas import MeetCreate, MeetResponse, MeetSettingsUpdate


RANGES = [["2026-08-14T10:00:00+00:00", "2026-08-14T12:00:00+00:00"]]
USER_ID = str(uuid4())


def test_create_accepts_camel_case_from_frontend():
    meeting = MeetCreate.model_validate(
        {
            "name": "Созвон",
            "dataRange": RANGES,
            "invitedUserIds": [USER_ID],
        }
    )
    assert meeting.data_range == RANGES
    assert str(meeting.invited_user_ids[0]) == USER_ID


def test_create_accepts_snake_case_from_old_clients():
    meeting = MeetCreate.model_validate(
        {
            "name": "Созвон",
            "data_range": RANGES,
            "invited_user_ids": [USER_ID],
        }
    )
    assert meeting.data_range == RANGES
    assert str(meeting.invited_user_ids[0]) == USER_ID


def test_create_json_out_is_camel_case():
    meeting = MeetCreate.model_validate(
        {"name": "Созвон", "dataRange": RANGES, "invitedUserIds": [USER_ID]}
    )
    payload = meeting.model_dump()
    assert payload["dataRange"] == RANGES
    assert "data_range" not in payload
    assert "invitedUserIds" in payload
    assert "invited_user_ids" not in payload


def test_orm_create_uses_column_names_not_json_aliases():
    meeting = MeetCreate.model_validate(
        {
            "name": "Созвон",
            "description": "текст",
            "dataRange": RANGES,
            "invitedUserIds": [USER_ID],
        }
    )
    record = Meetings(
        name=meeting.name,
        description=meeting.description,
        link=meeting.link,
        duration=meeting.duration,
        data_range=meeting.data_range or [],
        invited_user_ids=[
            str(item) for item in (meeting.invited_user_ids or [])
        ],
    )
    assert record.data_range == RANGES
    assert record.invited_user_ids == [USER_ID]


def test_response_reads_orm_snake_case_and_dumps_camel_case():
    record = SimpleNamespace(
        id=uuid4(),
        name="Созвон",
        description=None,
        link=None,
        duration=None,
        data_range=RANGES,
        invited_user_ids=[],
        slots=[],
        anyone_can_edit=True,
        anyone_can_delete_participants=True,
        require_login_to_vote=False,
        anyone_can_set_final=False,
        final_slot=None,
        observers=[],
        owner_id=None,
    )
    response = MeetResponse.model_validate(record)
    payload = response.model_dump()
    assert payload["dataRange"] == RANGES
    assert payload["hash"] == record.id
    assert payload["isCreator"] is None


def test_settings_accept_camel_and_snake():
    camel = MeetSettingsUpdate.model_validate(
        {
            "anyoneCanEdit": False,
            "anyoneCanDeleteParticipants": False,
            "requireLoginToVote": True,
            "anyoneCanSetFinal": True,
        }
    )
    snake = MeetSettingsUpdate.model_validate(
        {
            "anyone_can_edit": False,
            "anyone_can_delete_participants": False,
            "require_login_to_vote": True,
            "anyone_can_set_final": True,
        }
    )
    assert camel.anyone_can_edit is False
    assert snake.require_login_to_vote is True
