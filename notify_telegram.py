"""Отправка уведомлений в Telegram через Bot API."""
from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NOTIFY_TELEGRAM_BOT_TOKEN = os.getenv("NOTIFY_TELEGRAM_BOT_TOKEN", "").strip()


def is_configured() -> bool:
    return bool(NOTIFY_TELEGRAM_BOT_TOKEN)


def send_mention_notification(chat_id: str, keyword: str, message: str, message_link: str | None) -> bool:
    """Отправить уведомление о новом упоминании в Telegram (Bot API sendMessage)."""
    if not is_configured():
        logger.debug("NOTIFY_TELEGRAM_BOT_TOKEN не задан, пропуск Telegram-уведомления")
        return False
    text = f"🔔 Упоминание: {keyword}\n\n{message[:400]}{'...' if len(message) > 400 else ''}"
    if message_link:
        text += f"\n\n{message_link}"
    url = f"https://api.telegram.org/bot{NOTIFY_TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                logger.info("Telegram-уведомление об упоминании отправлено в chat_id=%s", chat_id)
                return True
            logger.warning("Telegram API вернул %s", resp.status)
            return False
    except Exception as e:
        logger.exception("Ошибка отправки Telegram-уведомления: %s", e)
        return False
