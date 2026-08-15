from datetime import datetime, timezone

from backend.src.meetings.suggest_final import suggest_windows


def test_suggest_picks_overlap_of_two():
    slots = [
        {
            "name": "Аня",
            "slots": [["2026-08-16T11:00:00Z", "2026-08-16T12:30:00Z"]],
        },
        {
            "name": "Боря",
            "slots": [["2026-08-16T11:30:00Z", "2026-08-16T12:30:00Z"]],
        },
    ]
    windows = suggest_windows(slots, "1 час", limit=3)
    assert windows
    assert windows[0]["people"] == 2
    assert windows[0]["slots"][0][0] == "2026-08-16T11:30:00Z"
    assert windows[0]["slots"][0][1] == "2026-08-16T12:00:00Z"


def test_suggest_duration_60_same_as_one_hour():
    slots = [
        {
            "name": "Аня",
            "slots": [["2026-08-16T11:00:00Z", "2026-08-16T12:30:00Z"]],
        },
        {
            "name": "Боря",
            "slots": [["2026-08-16T11:30:00Z", "2026-08-16T12:30:00Z"]],
        },
    ]
    by_hour = suggest_windows(slots, "1 час", limit=1)
    by_number = suggest_windows(slots, "60", limit=1)
    assert by_hour[0]["slots"] == by_number[0]["slots"]


def test_suggest_empty_without_votes():
    assert suggest_windows([], "30 мин") == []


def test_suggest_respects_duration_30():
    slots = [
        {
            "name": "Аня",
            "slots": [["2026-08-16T11:00:00Z", "2026-08-16T12:00:00Z"]],
        }
    ]
    windows = suggest_windows(slots, "30 мин", limit=1)
    assert windows[0]["slots"][0][0] == windows[0]["slots"][0][1]
    start = datetime.fromisoformat(
        windows[0]["slots"][0][0].replace("Z", "+00:00")
    )
    assert start.tzinfo is not None
    assert start.tzinfo.utcoffset(start) == timezone.utc.utcoffset(start)
