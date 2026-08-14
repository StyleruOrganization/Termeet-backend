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


def can_vote(record, user: UserSchema | None) -> bool:
    if has_final_slot(record):
        return False
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
        if item.get("user_id")
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
