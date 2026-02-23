"""
Уведомления о новых упоминаниях: отдельный модуль с нуля.

- Единственная точка входа: enqueue_mention_notification(mention_id).
- Парсер после создания Mention в БД вызывает enqueue_mention_notification(mention.id).
- Обработка выполняется в отдельном потоке: загрузка Mention и настроек из БД,
  проверка режима (all / leads_only / digest), отправка email и/или Telegram.
- Никакой передачи payload из парсера — всё берётся из БД по mention_id.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from database import SessionLocal
from models import Mention, NotificationSettings, User

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mention_notify")


def _get_or_create_settings(db, user_id: int):
    """Получить настройки уведомлений пользователя; при отсутствии создать с дефолтами."""
    row = db.scalar(select(NotificationSettings).where(NotificationSettings.user_id == user_id))
    if row is not None:
        return row
    settings = NotificationSettings(
        user_id=user_id,
        notify_email=True,
        notify_telegram=False,
        notify_mode="all",
        telegram_chat_id=None,
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _message_link_from_mention(m: Mention) -> str | None:
    """Собрать ссылку на сообщение по полям Mention (Telegram)."""
    msg_id = getattr(m, "message_id", None)
    if msg_id is None:
        return None
    username = (getattr(m, "chat_username", None) or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}/{msg_id}"
    cid = getattr(m, "chat_id", None)
    if cid is not None:
        aid = abs(int(cid))
        part = aid % (10**10) if aid >= 10**10 else aid
        return f"tg://privatepost?channel={part}&post={msg_id}"
    return None


def _send_for_mention(mention_id: int) -> None:
    """
    Загрузить упоминание из БД, проверить настройки пользователя и отправить
    email/Telegram. Вызывается из потока пула.
    """
    logger.info("Уведомление: обработка mention_id=%s", mention_id)
    try:
        with SessionLocal() as db:
            mention = db.get(Mention, mention_id)
            if mention is None:
                logger.warning("Уведомление: упоминание id=%s не найдено в БД (возможно, ещё не закоммичено)", mention_id)
                return
            user_id = mention.user_id
            settings = _get_or_create_settings(db, user_id)

            if not settings.notify_email and not settings.notify_telegram:
                logger.info("Уведомление mention_id=%s user_id=%s: пропуск — оба канала выключены", mention_id, user_id)
                return

            mode = (settings.notify_mode or "all").strip()
            is_lead = bool(getattr(mention, "is_lead", False))
            if mode == "leads_only" and not is_lead:
                logger.info("Уведомление mention_id=%s: пропуск — режим «только лиды», упоминание не лид", mention_id)
                return
            if mode == "digest":
                logger.info("Уведомление mention_id=%s: пропуск — режим «дайджест»", mention_id)
                return

            keyword = (mention.keyword_text or "").strip() or "—"
            message = (mention.message_text or "").strip()
            message_link = _message_link_from_mention(mention)

            if settings.notify_email:
                user = db.scalar(select(User).where(User.id == user_id))
                email = (user and getattr(user, "email", None) or "").strip()
                if email:
                    try:
                        from email_sender import send_mention_notification_email
                        ok = send_mention_notification_email(email, keyword, message, message_link)
                        if ok:
                            logger.info("Уведомление mention_id=%s: email отправлен на %s", mention_id, email)
                        else:
                            logger.warning("Уведомление mention_id=%s: отправка email вернула False", mention_id)
                    except Exception as e:
                        logger.exception("Уведомление mention_id=%s: ошибка email — %s", mention_id, e)
                else:
                    logger.debug("Уведомление mention_id=%s: email пользователя не задан", mention_id)

            if settings.notify_telegram:
                chat_id = (settings.telegram_chat_id or "").strip()
                if not chat_id:
                    logger.warning("Уведомление mention_id=%s user_id=%s: Telegram включён, но Chat ID не задан", mention_id, user_id)
                else:
                    try:
                        import notify_telegram
                        ok = notify_telegram.send_mention_notification(chat_id, keyword, message, message_link)
                        if ok:
                            logger.info("Уведомление mention_id=%s: Telegram доставлено chat_id=%s", mention_id, chat_id)
                        else:
                            logger.warning("Уведомление mention_id=%s: Telegram не доставлено chat_id=%s", mention_id, chat_id)
                    except Exception as e:
                        logger.exception("Уведомление mention_id=%s: ошибка Telegram — %s", mention_id, e)
    except Exception as e:
        logger.exception("Уведомление mention_id=%s: неожиданная ошибка — %s", mention_id, e)


def enqueue_mention_notification(mention_id: int) -> None:
    """
    Поставить в очередь отправку уведомлений по упоминанию.
    Вызывать из парсера сразу после commit (когда упоминание уже в БД).
    """
    logger.info("Уведомление: в очередь mention_id=%s", mention_id)
    try:
        _EXECUTOR.submit(_send_for_mention, mention_id)
    except Exception as e:
        logger.exception("Не удалось поставить уведомление mention_id=%s в очередь: %s", mention_id, e)
        try:
            _send_for_mention(mention_id)
        except Exception:
            logger.exception("Прямая отправка уведомления mention_id=%s также завершилась ошибкой", mention_id)
