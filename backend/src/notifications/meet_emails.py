import logging
from textwrap import dedent
from urllib.parse import urlparse

from backend.src.auth.utils import send_email
from backend.src.config import config
from backend.src.jinja_templates import templates

logger = logging.getLogger(__name__)


def front_origin() -> str:
    parsed = urlparse(config.email.VERIFICATION_LINK or "")
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "https://termeet-dev.ru"


def meet_url(meeting_hash) -> str:
    return f"{front_origin()}/meet/{meeting_hash}"


async def send_meet_email(
    recipient: str, subject: str, heading: str, body: str, cta: str
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
) -> None:
    link = meet_url(meeting_hash)
    extra = f" Ссылка на звонок: {join_link}" if join_link else ""
    seen: set[str] = set()
    for email in emails:
        if not email or email in seen:
            continue
        seen.add(email)
        await send_meet_email(
            recipient=email,
            subject=f"Назначено время: {meeting_name}",
            heading="Итоговое время встречи",
            body=(
                f"Для встречи «{meeting_name}» выбрали итоговое время. "
                f"Откройте сетку, фиолетовые ячейки — это оно.{extra}"
            ),
            cta=link,
        )
