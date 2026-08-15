from types import SimpleNamespace

from backend.src.meetings.permissions import (
    expected_voter_ids,
    voted_user_ids,
)


def test_expected_skips_owner_observers_and_guests():
    owner = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    invited = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    observer = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    record = SimpleNamespace(
        owner_id=owner,
        invited_user_ids=[invited, observer],
        team=None,
        observers=[{"user_id": observer}],
        slots=[
            {"name": "Гость", "user_id": None},
            {"name": "Вася", "user_id": invited},
        ],
    )
    assert expected_voter_ids(record) == {invited}
    assert voted_user_ids(record) == {invited}
    assert expected_voter_ids(record) <= voted_user_ids(record)


def test_expected_empty_without_invites():
    record = SimpleNamespace(
        owner_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        invited_user_ids=[],
        team=None,
        observers=[],
        slots=[{"name": "Гость", "user_id": None}],
    )
    assert expected_voter_ids(record) == set()
