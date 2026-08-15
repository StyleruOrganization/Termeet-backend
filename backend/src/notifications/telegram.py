import logging

import httpx

from backend.src.config import config

logger = logging.getLogger(__name__)


async def send_telegram_message(telegram_user_id: int | None, text: str) -> bool:
    token = (config.telegram_bot.TOKEN or "").strip()
    if not token or not telegram_user_id or not text:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": telegram_user_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            if response.status_code >= 400:
                logger.warning(
                    "telegram notify %s: %s %s",
                    telegram_user_id,
                    response.status_code,
                    response.text[:200],
                )
                return False
            return True
    except Exception:
        logger.exception("telegram notify failed to %s", telegram_user_id)
        return False
