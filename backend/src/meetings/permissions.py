from datetime import datetime, timezone

from backend.src.users.schemas import UserSchema


def is_open_meeting(record) -> bool:
    return record.owner_id is None


def is_owner(record, user: UserSchema | None) -> bool:
    if user is None or record.owner_id is None:
        return False
    return str(record.owner_id) == str(user.id)


def anyone_can_edit(record) -> bool:
    return bool(getattr(record, "anyone_can_edit", True))


def anyone_can_delete(record) -> bool:
    return bool(getattr(record, "anyone_can_delete_participants", True))


def require_login_to_vote(record) -> bool:
    return bool(getattr(record, "require_login_to_vote", False))


def is_closed_meeting(record) -> bool:
    return bool(getattr(record, "is_closed", False))


def invite_only_vote(record) -> bool:
    return bool(getattr(record, "invite_only_vote", False)) or is_closed_meeting(
        record
    )


def invited_user_ids(record) -> set[str]:
    return {
        str(item)
        for item in (getattr(record, "invited_user_ids", None) or [])
        if item
    }


def team_member_ids(record) -> set[str]:
    team = getattr(record, "team", None)
    if team is None:
        return set()
    ids = {str(team.user_id)}
    for member in getattr(team, "members", None) or []:
        ids.add(str(member.id))
    return ids


def voted_user_ids(record) -> set[str]:
    return {
        str(item.get("user_id"))
        for item in (getattr(record, "slots", None) or [])
        if isinstance(item, dict) and item.get("user_id")
    }


def expected_voter_ids(record) -> set[str]:
    ids = invited_user_ids(record) | team_member_ids(record)
    ids -= observer_user_ids(record)
    if getattr(record, "owner_id", None):
        ids.discard(str(record.owner_id))
    return ids


def is_added_to_meeting(record, user: UserSchema | None) -> bool:
    if user is None:
        return False
    if is_owner(record, user):
        return True
    user_id = str(user.id)
    if user_id in invited_user_ids(record):
        return True
    if user_id in team_member_ids(record):
        return True
    return has_user_slots(record, user)


def can_view_meeting(record, user: UserSchema | None) -> bool:
    if not is_closed_meeting(record):
        return True
    return is_added_to_meeting(record, user)


def can_edit_meet(record, user: UserSchema | None) -> bool:
    if is_open_meeting(record) or is_owner(record, user):
        return True
    return anyone_can_edit(record)


def can_delete_participants(record, user: UserSchema | None) -> bool:
    if is_open_meeting(record) or is_owner(record, user):
        return True
    return anyone_can_delete(record)


def can_edit_settings(record, user: UserSchema | None) -> bool:
    return is_owner(record, user)


def has_final_slot(record) -> bool:
    return bool(getattr(record, "final_slot", None))


def anyone_can_set_final(record) -> bool:
    return bool(getattr(record, "anyone_can_set_final", False))


def vote_deadline_passed(record) -> bool:
    deadline = getattr(record, "vote_deadline", None)
    if deadline is None:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= deadline


def lock_vote_after_deadline(record) -> bool:
    return bool(getattr(record, "lock_vote_after_deadline", False))


def can_vote(record, user: UserSchema | None) -> bool:
    if has_final_slot(record):
        return False
    if lock_vote_after_deadline(record) and vote_deadline_passed(record):
        return False
    if is_closed_meeting(record) or invite_only_vote(record):
        return is_added_to_meeting(record, user)
    if is_open_meeting(record) or not require_login_to_vote(record):
        return True
    return user is not None


def can_set_final(record, user: UserSchema | None) -> bool:
    if user is None:
        return False
    if is_owner(record, user) or is_open_meeting(record):
        return True
    return anyone_can_set_final(record)


def observer_user_ids(record) -> set[str]:
    return {
        str(item.get("user_id"))
        for item in (getattr(record, "observers", None) or [])
        if isinstance(item, dict) and item.get("user_id")
    }


def has_user_slots(record, user: UserSchema | None) -> bool:
    if user is None:
        return False
    user_id = str(user.id)
    for slot in record.slots or []:
        if str(slot.get("user_id")) == user_id:
            return True
    return False


def organizer_slot_name(record) -> str | None:
    if record.owner_id is None:
        return None
    owner_id = str(record.owner_id)
    for slot in record.slots or []:
        if str(slot.get("user_id")) == owner_id:
            return slot.get("name")
    return None
