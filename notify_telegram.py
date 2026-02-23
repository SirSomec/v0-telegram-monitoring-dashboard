"""Отправка уведомлений в Telegram через Bot API. Бот: @telescopemsg_bot."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Основной бот уведомлений (указывать в документации и интерфейсе)
TELEGRAM_BOT_USERNAME = "telescopemsg_bot"

NOTIFY_TELEGRAM_BOT_TOKEN = os.getenv("NOTIFY_TELEGRAM_BOT_TOKEN", "").strip()
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()


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
        logger.info("Уведомления Telegram отключены: NOTIFY_TELEGRAM_BOT_TOKEN не задан в окружении, пропуск отправки")
        return False
    url = f"https://api.telegram.org/bot{NOTIFY_TELEGRAM_BOT_TOKEN}/sendMessage"
    payload: dict[str, str | int | bool] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    data = urllib.parse.urlencode(payload, encoding="utf-8").encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
    try:
        logger.debug("Telegram sendMessage: запрос chat_id=%s text_len=%s", chat_id, len(text))
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                logger.debug("Telegram sendMessage: успех chat_id=%s", chat_id)
                return True
            body = resp.read().decode("utf-8", errors="replace")
            logger.warning("Telegram API sendMessage вернул %s: %s", resp.status, body[:500])
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        try:
            err = json.loads(body)
            desc = err.get("description", body)
        except Exception:
            desc = body or str(e)
        logger.warning("Telegram API ошибка (chat_id=%s, status=%s): %s", chat_id, e.code, desc)
        return False
    except Exception as e:
        logger.exception("Ошибка отправки сообщения в Telegram (chat_id=%s): %s", chat_id, e)
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
    """Отправить уведомление о новом упоминании в Telegram (Bot API sendMessage).
    Ссылки tg://privatepost не используются — у получателя часто «нет доступа».
    Для публичных чатов — кнопка «Открыть сообщение» (t.me/...), иначе — «Открыть в дашборде».
    """
    if not is_configured():
        logger.info("Telegram-уведомление об упоминании пропущено: NOTIFY_TELEGRAM_BOT_TOKEN не задан")
        return False
    text = f"🔔 Упоминание: {keyword}\n\n{message[:400]}{'...' if len(message) > 400 else ''}"
    reply_markup = None
    if message_link and message_link.startswith("https://t.me/"):
        reply_markup = {"inline_keyboard": [[{"text": "Открыть сообщение", "url": message_link}]]}
    elif FRONTEND_URL:
        dashboard_url = f"{FRONTEND_URL.rstrip('/')}/dashboard"
        reply_markup = {"inline_keyboard": [[{"text": "Открыть в дашборде", "url": dashboard_url}]]}
    if send_message(chat_id, text, reply_markup=reply_markup):
        logger.info("Telegram-уведомление об упоминании отправлено в chat_id=%s", chat_id)
        return True
    return False


def send_support_notification(
    chat_id: str | int,
    ticket_id: int,
    user_email: str | None,
    user_name: str | None,
    subject: str,
    message_preview: str,
) -> bool:
    """Уведомить администратора о новом сообщении в обращении поддержки."""
    if not is_configured():
        logger.info("Уведомление поддержки в Telegram пропущено: NOTIFY_TELEGRAM_BOT_TOKEN не задан")
        return False
    who = (user_name or user_email or "Пользователь").strip()
    preview = (message_preview or "").strip()[:200]
    if len((message_preview or "").strip()) > 200:
        preview += "..."
    text = (
        "📩 Новое обращение в поддержку\n\n"
        f"От: {who}\n"
        f"Тема: {subject}\n\n"
        f"{preview}"
    )
    if send_message(chat_id, text):
        logger.info("Уведомление о поддержке отправлено в chat_id=%s, тикет #%s", chat_id, ticket_id)
        return True
    return False


def send_support_reply_to_user(chat_id: str | int, ticket_subject: str, reply_preview: str) -> bool:
    """Уведомить пользователя об ответе поддержки в Telegram."""
    if not is_configured():
        logger.info("Уведомление об ответе поддержки в Telegram пропущено: NOTIFY_TELEGRAM_BOT_TOKEN не задан")
        return False
    preview = (reply_preview or "").strip()[:250]
    if len((reply_preview or "").strip()) > 250:
        preview += "..."
    text = (
        "📩 Ответ по обращению в поддержку\n\n"
        f"Тема: {ticket_subject}\n\n"
        f"{preview}\n\n"
        "Откройте раздел «Поддержка» в личном кабинете, чтобы прочитать полный ответ."
    )
    if send_message(chat_id, text):
        logger.info("Уведомление об ответе поддержки отправлено в chat_id=%s", chat_id)
        return True
    return False
