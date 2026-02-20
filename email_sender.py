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

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes")
FRONTEND_URL = os.getenv("FRONTEND_URL", "").strip()  # Базовый URL фронта для ссылок в письмах


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
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info("Письмо для сброса пароля отправлено на %s", to_email)
        return True
    except Exception as e:
        logger.exception("Ошибка отправки email для сброса пароля: %s", e)
        return False
