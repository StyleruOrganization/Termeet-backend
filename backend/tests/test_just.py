from textwrap import dedent
import asyncio
from aiosmtplib import SMTP

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.src.users.schemas import UserSchema


async def send_email(
    recipient: str, subject: str, plain_content: str, html_content: str = ""
):
    message = MIMEMultipart("alternative")
    message["From"] = "maklakov.daniils@yandex.ru"
    message["To"] = recipient
    message["Subject"] = subject

    plain_text_message = MIMEText(
        plain_content,
        "plain",
        "utf-8",
    )
    message.attach(plain_text_message)

    if html_content:
        html_message = MIMEText(
            html_content,
            "html",
            "utf-8",
        )
        message.attach(html_message)

    smtp_client = SMTP(hostname="smtp.yandex.ru", port=465, use_tls=True)

    async with smtp_client:
        await smtp_client.login(
            "maklakov.daniils@yandex.ru", "efkyznqxejhluixj"
        )
        await smtp_client.send_message(message)
        print("Письмо успешно отправлено!")


async def send_verification_email(
        user: UserSchema,
        verification_link: str,
):
    recipient = user.email

    subject = "Подтверждение письма"

    plain_content = dedent(
        f"""\
        Дорогой(-ая) {recipient},

        Please перейдите по ссылке, чтобы подтвердить свою почту:
        {verification_link}
        """
    )

    html_content = ...
    await send_email(
        recipient=recipient,
        subject=subject,
        plain_content=plain_content,
        html_content=html_content
    )


def test_smtp():
    asyncio.run(
        send_email(
            "dpmaklakov@edu.hse.ru",
            "Подтверждение письма",
            "Йоу-йоу, успешный успех от тестового Termeet-а",
        )
    )

    # message = MIMEMultipart("alternative")
    # message["From"] = "maklakov.daniils@yandex.ru"
    # message["To"] = recip
    # efkyznqxejhluixj  # noqa
