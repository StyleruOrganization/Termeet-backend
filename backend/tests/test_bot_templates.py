from datetime import date

from backend.src.bot_templates.parse import parse_tokens, timezone_offset_hours
from backend.src.bot_templates.schema import BotTemplate, validate_template_list


def _daily(**extra) -> BotTemplate:
    payload = {
        "slug": "daily",
        "name": "Дейлик {date}",
        "aliases_today": ["td", "today"],
        "aliases_tomorrow": ["tmrw"],
        "aliases_day_after": ["dat"],
        "people_min": 0,
        "people_max": 0,
    }
    payload.update(extra)
    return BotTemplate.model_validate(payload)


def test_offset_from_cabinet_label():
    assert timezone_offset_hours("UTC +3:00 (Москва)") == 3
    assert timezone_offset_hours("UTC +10:00 (Владивосток)") == 10
    assert timezone_offset_hours("UTC -5:00") == -5


def test_any_order_date_and_time():
    template = _daily(time_mode="optional")
    today = date(2026, 8, 16)
    first = parse_tokens(template, ["td", "16:00"], today)
    second = parse_tokens(template, ["16:00", "td"], today)
    assert first["date"] == second["date"] == today
    assert first["time"] == second["time"] == "16:00"


def test_custom_alias_not_builtin_tomorrow():
    template = _daily()
    today = date(2026, 8, 16)
    parsed = parse_tokens(template, ["tmrw"], today)
    assert parsed["date"] == date(2026, 8, 17)
    try:
        parse_tokens(template, ["tomorrow"], today)
        assert False
    except ValueError:
        pass


def test_slug_cannot_match_alias():
    try:
        validate_template_list(
            [
                {
                    "slug": "td",
                    "name": "Bad",
                    "aliases_today": ["td"],
                }
            ]
        )
        assert False
    except ValueError:
        pass


def test_two_templates_cannot_share_alias():
    try:
        validate_template_list(
            [
                {
                    "slug": "daily",
                    "name": "A",
                    "aliases_today": ["td"],
                },
                {
                    "slug": "sync",
                    "name": "B",
                    "aliases_tomorrow": ["td"],
                },
            ]
        )
        assert False
    except ValueError:
        pass


def test_team_slug_and_calendar_date():
    template = _daily(team_mode="arg")
    today = date(2026, 8, 16)
    parsed = parse_tokens(template, ["frontend", "20.08.2026"], today)
    assert parsed["team_slug"] == "frontend"
    assert parsed["date"] == date(2026, 8, 20)
