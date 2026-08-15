import logging
from datetime import datetime, timedelta, timezone
from textwrap import dedent
from urllib.parse import urlparse

from backend.src.auth.utils import send_email
from backend.src.config import config
from backend.src.jinja_templates import templates

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


def front_origin() -> str:
    parsed = urlparse(config.email.VERIFICATION_LINK or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://termeet-dev.ru"


def meet_url(meeting_hash) -> str:
    return f"{front_origin()}/meet/{meeting_hash}"


def format_range(start: datetime, end: datetime) -> str:
    local_start = start.astimezone(MSK)
    local_end = end.astimezone(MSK)
    return (
        f"{local_start.strftime('%d.%m.%Y %H:%M')}–"
        f"{local_end.strftime('%H:%M')} (МСК)"
    )


async def send_meet_email(
    recipient: str,
    subject: str,
    heading: str,
    body: str,
    cta: str,
    ics_content: str | None = None,
) -> None:
    if not recipient:
        return
    plain = dedent(
        f"""\
        {heading}

        {body}

        {cta}
        """
    )
    try:
        template = templates.get_template("meet_event_email.html")
        html = template.render(
            heading=heading,
            body=body,
            cta_href=cta,
            cta_label="Открыть встречу",
        )
        await send_email(
            recipient=recipient,
            subject=subject,
            plain_content=plain,
            html_content=html,
            ics_content=ics_content,
        )
    except Exception:
        logger.exception("meet email failed to %s", recipient)


async def notify_owner_participant_voted(
    owner_email: str | None,
    owner_wants: bool,
    meeting_name: str,
    meeting_hash,
    participant_name: str,
) -> None:
    if not owner_wants or not owner_email:
        return
    link = meet_url(meeting_hash)
    await send_meet_email(
        recipient=owner_email,
        subject=f"Новый голос: {meeting_name}",
        heading="Участник выбрал время",
        body=(
            f"{participant_name} отметил слоты во встрече «{meeting_name}». "
            "Можно пересмотреть своё время на сетке."
        ),
        cta=link,
    )


async def notify_final_time(
    emails: list[str],
    meeting_name: str,
    meeting_hash,
    join_link: str | None,
    changed: bool = False,
    when_text: str | None = None,
    ics_content: str | None = None,
    skip_emails: set[str] | None = None,
) -> None:
    link = meet_url(meeting_hash)
    extra = f" Ссылка на звонок: {join_link}" if join_link else ""
    when = f" Время: {when_text}." if when_text else ""
    ics_note = " К письму приложен файл .ics — его можно открыть в календаре."
    if changed:
        subject = f"Время изменили: {meeting_name}"
        heading = "Итоговое время обновили"
        body = (
            f"Для встречи «{meeting_name}» выбрали другое итоговое время."
            f"{when} Откройте сетку, фиолетовые ячейки — это оно.{extra}"
            f"{ics_note}"
        )
    else:
        subject = f"Назначено время: {meeting_name}"
        heading = "Итоговое время встречи"
        body = (
            f"Для встречи «{meeting_name}» выбрали итоговое время."
            f"{when} Откройте сетку, фиолетовые ячейки — это оно.{extra}"
            f"{ics_note}"
        )
    skip = skip_emails or set()
    seen: set[str] = set()
    for email in emails:
        if not email or email in seen or email in skip:
            continue
        seen.add(email)
        await send_meet_email(
            recipient=email,
            subject=subject,
            heading=heading,
            body=body,
            cta=link,
            ics_content=ics_content,
        )


async def notify_calendar_conflict(
    recipient: str,
    meeting_name: str,
    meeting_hash,
    when_text: str,
    busy_titles: list[str],
    join_link: str | None,
    ics_content: str | None = None,
) -> None:
    if not recipient:
        return
    link = meet_url(meeting_hash)
    titles = ", ".join(f"«{title}»" for title in busy_titles if title) or (
        "другая встреча"
    )
    extra = f" Ссылка из Termeet: {join_link}." if join_link else ""
    await send_meet_email(
        recipient=recipient,
        subject=f"Пересечение по времени: {meeting_name}",
        heading="В это время у вас уже есть встреча в Яндекс Календаре",
        body=(
            f"Для «{meeting_name}» назначили итоговое время {when_text}. "
            f"В Яндекс Календаре на это же окно уже стоит {titles}. "
            "Если не получится прийти — напишите организатору или откройте "
            "сетку Termeet и поправьте своё время, пока можно. "
            "Событие Termeet всё равно добавили в ваш календарь, "
            "чтобы окно было видно."
            f"{extra}"
        ),
        cta=link,
        ics_content=ics_content,
    )
