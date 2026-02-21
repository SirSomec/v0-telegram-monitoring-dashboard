"""Отправка уведомлений в Telegram через Bot API. Бот: @telescopemsg_bot."""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Основной бот уведомлений (указывать в документации и интерфейсе)
TELEGRAM_BOT_USERNAME = "telescopemsg_bot"

NOTIFY_TELEGRAM_BOT_TOKEN = os.getenv("NOTIFY_TELEGRAM_BOT_TOKEN", "").strip()


def is_configured() -> bool:
    return bool(NOTIFY_TELEGRAM_BOT_TOKEN)


def send_message(
    chat_id: str | int,
    text: str,
    *,
    disable_web_page_preview: bool = True,
    reply_markup: dict | None = None,
) -> bool:
    """Отправить сообщение от бота (Bot API sendMessage). reply_markup — например inline_keyboard."""
    if not is_configured():
        logger.debug("NOTIFY_TELEGRAM_BOT_TOKEN не задан, пропуск отправки")
        return False
    url = f"https://api.telegram.org/bot{NOTIFY_TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict[str, str | int | bool] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return True
            logger.warning("Telegram API sendMessage вернул %s", resp.status)
            return False
    except Exception as e:
        logger.exception("Ошибка отправки сообщения в Telegram: %s", e)
        return False


def answer_callback_query(callback_query_id: str, text: str | None = None) -> bool:
    """Ответить на callback_query (обязательно вызвать, иначе у пользователя крутится загрузка)."""
    if not is_configured():
        return False
    url = f"https://api.telegram.org/bot{NOTIFY_TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload: dict[str, str] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.exception("Ошибка answerCallbackQuery: %s", e)
        return False


def send_mention_notification(chat_id: str, keyword: str, message: str, message_link: str | None) -> bool:
    """Отправить уведомление о новом упоминании в Telegram (Bot API sendMessage)."""
    if not is_configured():
        logger.debug("NOTIFY_TELEGRAM_BOT_TOKEN не задан, пропуск Telegram-уведомления")
        return False
    text = f"🔔 Упоминание: {keyword}\n\n{message[:400]}{'...' if len(message) > 400 else ''}"
    if message_link:
        text += f"\n\n{message_link}"
    if send_message(chat_id, text):
        logger.info("Telegram-уведомление об упоминании отправлено в chat_id=%s", chat_id)
        return True
    return False
