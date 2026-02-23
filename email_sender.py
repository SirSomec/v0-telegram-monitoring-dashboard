"""Отправка email (восстановление пароля и т.д.). Использует SMTP из переменных окружения."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _log_email_error_to_parser(message: str) -> None:
    """Дублировать ошибку отправки email в лог парсера (для отображения в админке)."""
    try:
        from parser_log import append as parser_log_append
        parser_log_append(f"Email: {message}")
    except Exception:
        pass

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes")
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "20"))  # Таймаут в секундах; быстрый фейл, чтобы не держать воркеры уведомлений
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()  # Базовый URL фронта для ссылок в письмах


def _smtp_connection():
    """
    Контекстный менеджер: SMTP-подключение с учётом порта.
    Порт 465 — сразу SSL (SMTP_SSL), иначе — обычный SMTP + STARTTLS при SMTP_USE_TLS.
    """
    if SMTP_PORT == 465:
        return smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)
    if SMTP_USE_TLS:
        server.starttls()
    return server


def is_configured() -> bool:
    """Проверка, настроена ли отправка email."""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Отправить письмо со ссылкой для сброса пароля.
    Возвращает True при успехе, False при ошибке. Если SMTP не настроен — логирует ссылку и возвращает True.
    """
    subject = "TeleScope — восстановление пароля"
    body_plain = (
        f"Здравствуйте.\n\n"
        f"Вы запросили сброс пароля для аккаунта TeleScope.\n\n"
        f"Перейдите по ссылке, чтобы задать новый пароль:\n{reset_link}\n\n"
        f"Ссылка действительна 1 час. Если вы не запрашивали сброс, проигнорируйте это письмо.\n\n"
        f"— TeleScope"
    )
    body_html = (
        f"<p>Здравствуйте.</p>"
        f"<p>Вы запросили сброс пароля для аккаунта TeleScope.</p>"
        f"<p><a href=\"{reset_link}\">Задать новый пароль</a></p>"
        f"<p>Ссылка действительна 1 час. Если вы не запрашивали сброс, проигнорируйте это письмо.</p>"
        f"<p>— TeleScope</p>"
    )

    if not is_configured():
        logger.warning(
            "SMTP не настроен (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). Ссылка для сброса пароля (для теста): %s",
            reset_link,
        )
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with _smtp_connection() as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Письмо для сброса пароля отправлено на %s", to_email)
        return True
    except Exception as e:
        err_msg = f"Ошибка отправки email для сброса пароля: {e}"
        logger.exception("%s", err_msg)
        _log_email_error_to_parser(err_msg)
        return False


def send_test_email(to_email: str) -> bool:
    """
    Отправить тестовое письмо на указанный адрес (для проверки настройки SMTP).
    Возвращает True при успехе, False при ошибке. Ошибки пишутся в лог парсера.
    """
    if not is_configured():
        _log_email_error_to_parser("SMTP не настроен (SMTP_HOST, SMTP_USER, SMTP_PASSWORD). Тестовое письмо не отправлено.")
        return False

    subject = "TeleScope — тестовое письмо"
    body_plain = (
        "Здравствуйте.\n\n"
        "Это тестовое письмо от TeleScope. Отправка почты настроена корректно.\n\n"
        "— TeleScope"
    )
    body_html = (
        "<p>Здравствуйте.</p>"
        "<p>Это тестовое письмо от TeleScope. Отправка почты настроена корректно.</p>"
        "<p>— TeleScope</p>"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with _smtp_connection() as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Тестовое письмо отправлено на %s", to_email)
        return True
    except Exception as e:
        err_msg = f"Ошибка отправки тестового письма на {to_email}: {e}"
        logger.exception("%s", err_msg)
        _log_email_error_to_parser(err_msg)
        return False


def send_mention_notification_email(to_email: str, keyword: str, message: str, message_link: str | None) -> bool:
    """Отправить уведомление о новом упоминании на email."""
    subject = f"TeleScope — новое упоминание: {keyword[:50]}"
    body_plain = (
        f"Ключевое слово: {keyword}\n\n"
        f"Сообщение: {message[:500]}{'...' if len(message) > 500 else ''}\n\n"
    )
    if message_link:
        body_plain += f"Ссылка на сообщение: {message_link}\n\n"
    body_plain += "— TeleScope"
    body_html = (
        f"<p><strong>Ключевое слово:</strong> {keyword}</p>"
        f"<p>{message[:500].replace(chr(10), '<br>')}{'...' if len(message) > 500 else ''}</p>"
    )
    if message_link:
        body_html += f'<p><a href="{message_link}">Открыть сообщение в Telegram</a></p>'
    body_html += "<p>— TeleScope</p>"

    if not is_configured():
        logger.debug("SMTP не настроен, пропуск email-уведомления об упоминании")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with _smtp_connection() as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Уведомление об упоминании отправлено на %s", to_email)
        return True
    except Exception as e:
        err_msg = f"Ошибка отправки email-уведомления об упоминании: {e}"
        logger.exception("%s", err_msg)
        _log_email_error_to_parser(err_msg)
        return False


def send_support_reply_email(to_email: str, ticket_subject: str, reply_preview: str) -> bool:
    """Уведомить пользователя об ответе поддержки на обращение."""
    subject = f"TeleScope — ответ по обращению: {ticket_subject[:50]}"
    dashboard_hint = f"Откройте раздел «Поддержка» в личном кабинете: {FRONTEND_URL.rstrip('/')}/dashboard" if FRONTEND_URL else "Откройте раздел «Поддержка» в личном кабинете."
    body_plain = (
        f"Здравствуйте.\n\n"
        f"По вашему обращению «{ticket_subject}» получен ответ от поддержки.\n\n"
        f"Фрагмент ответа:\n{reply_preview[:400]}{'...' if len(reply_preview) > 400 else ''}\n\n"
        f"{dashboard_hint}\n\n"
        f"— TeleScope"
    )
    body_html = (
        f"<p>Здравствуйте.</p>"
        f"<p>По вашему обращению «<strong>{ticket_subject}</strong>» получен ответ от поддержки.</p>"
        f"<p>{reply_preview[:400].replace(chr(10), '<br>')}{'...' if len(reply_preview) > 400 else ''}</p>"
        f"<p>{dashboard_hint}</p>"
        f"<p>— TeleScope</p>"
    )

    if not is_configured():
        logger.debug("SMTP не настроен, пропуск email об ответе поддержки")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with _smtp_connection() as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Уведомление об ответе поддержки отправлено на %s", to_email)
        return True
    except Exception as e:
        err_msg = f"Ошибка отправки email об ответе поддержки: {e}"
        logger.exception("%s", err_msg)
        _log_email_error_to_parser(err_msg)
        return False
