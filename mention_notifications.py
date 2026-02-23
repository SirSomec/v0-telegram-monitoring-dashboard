"""
Уведомления о новых упоминаниях: отдельный модуль с нуля.

- Единственная точка входа: enqueue_mention_notification(mention_id).
- Парсер после создания Mention в БД вызывает enqueue_mention_notification(mention.id).
- Обработка выполняется в отдельных воркерах: очередь с неблокирующей постановкой,
  чтобы парсер и лента никогда не ждали отправку email/Telegram.
- Никакой передачи payload из парсера — всё берётся из БД по mention_id.
"""
from __future__ import annotations

import logging
import queue
import threading

from sqlalchemy import select

from database import SessionLocal
from models import Mention, NotificationSettings, User

logger = logging.getLogger(__name__)

_NOTIFY_QUEUE: queue.Queue[int | None] = queue.Queue(maxsize=2000)
_NUM_WORKERS = 4


def _notification_worker() -> None:
    """Воркер: забирает mention_id из очереди и отправляет уведомления. None — сигнал выхода."""
    while True:
        try:
            mention_id = _NOTIFY_QUEUE.get()
            if mention_id is None:
                break
            _send_for_mention(mention_id)
        except Exception as e:
            logger.exception("Воркер уведомлений: %s", e)


def _start_workers() -> None:
    for i in range(_NUM_WORKERS):
        t = threading.Thread(target=_notification_worker, name=f"mention_notify_{i}", daemon=True)
        t.start()


_start_workers()


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
    Важно: сессию БД закрываем до отправки email/Telegram, чтобы долгий SMTP-таймаут
    не блокировал соединения из пула и не мешал парсеру и API.
    """
    logger.info("Уведомление: обработка mention_id=%s", mention_id)
    try:
        # Собираем все данные в рамках сессии и сразу освобождаем соединение
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
            send_email = bool(settings.notify_email)
            email = ""
            if send_email:
                user = db.scalar(select(User).where(User.id == user_id))
                email = (user and getattr(user, "email", None) or "").strip()
            send_telegram = bool(settings.notify_telegram)
            telegram_chat_id = (settings.telegram_chat_id or "").strip()
        # Сессия закрыта — отправка email/Telegram без удержания соединения БД

        if send_email and email:
            try:
                from email_sender import send_mention_notification_email
                ok = send_mention_notification_email(email, keyword, message, message_link)
                if ok:
                    logger.info("Уведомление mention_id=%s: email отправлен на %s", mention_id, email)
                else:
                    logger.warning("Уведомление mention_id=%s: отправка email вернула False", mention_id)
            except Exception as e:
                logger.exception("Уведомление mention_id=%s: ошибка email — %s", mention_id, e)
        elif send_email:
            logger.debug("Уведомление mention_id=%s: email пользователя не задан", mention_id)

        if send_telegram:
            if not telegram_chat_id:
                logger.warning("Уведомление mention_id=%s user_id=%s: Telegram включён, но Chat ID не задан", mention_id, user_id)
            else:
                try:
                    import notify_telegram
                    ok = notify_telegram.send_mention_notification(telegram_chat_id, keyword, message, message_link)
                    if ok:
                        logger.info("Уведомление mention_id=%s: Telegram доставлено chat_id=%s", mention_id, telegram_chat_id)
                    else:
                        logger.warning("Уведомление mention_id=%s: Telegram не доставлено chat_id=%s", mention_id, telegram_chat_id)
                except Exception as e:
                    logger.exception("Уведомление mention_id=%s: ошибка Telegram — %s", mention_id, e)
    except Exception as e:
        logger.exception("Уведомление mention_id=%s: неожиданная ошибка — %s", mention_id, e)


def enqueue_mention_notification(mention_id: int) -> None:
    """
    Поставить в очередь отправку уведомлений по упоминанию. Неблокирующая постановка:
    парсер и отображение ленты не ждут отправку email/Telegram. При переполнении очереди
    уведомление пропускается (лента и WS уже обновлены).
    """
    try:
        _NOTIFY_QUEUE.put_nowait(mention_id)
    except queue.Full:
        logger.warning("Очередь уведомлений переполнена, mention_id=%s пропущен", mention_id)
