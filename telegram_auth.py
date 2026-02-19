"""
Одноразовая авторизация Telegram через админку: запрос кода по номеру, ввод кода, сохранение сессии.
Состояние «ожидание кода» хранится в памяти (один процесс).
"""
from __future__ import annotations

from typing import Any

from telethon import TelegramClient
from telethon.sessions import StringSession

from parser_config import get_parser_setting_str, set_parser_setting

try:
    import socks
    _PROXY_AVAILABLE = True
except ImportError:
    _PROXY_AVAILABLE = False

# Состояние ожидания кода (один запрос за раз)
_pending: dict[str, Any] = {}


def _get_proxy() -> tuple | None:
    if not _PROXY_AVAILABLE:
        return None
    host = get_parser_setting_str("TG_PROXY_HOST")
    port_str = get_parser_setting_str("TG_PROXY_PORT")
    if not host or not port_str:
        return None
    try:
        port = int(port_str)
    except ValueError:
        return None
    user = get_parser_setting_str("TG_PROXY_USER") or None
    pwd = get_parser_setting_str("TG_PROXY_PASS") or None
    return (socks.SOCKS5, host, port, True, user, pwd)


async def request_code(phone: str) -> None:
    """
    Отправить код на номер. После вызова пользователь вводит код в админке и вызывает submit_code().
    Выбрасывает RuntimeError при неверных api_id/api_hash или номере.
    """
    global _pending
    if _pending:
        raise RuntimeError("Уже ожидается ввод кода. Введите код или подождите 5 минут.")
    phone = (phone or "").strip()
    if not phone:
        raise RuntimeError("Укажите номер телефона.")
    api_id = get_parser_setting_str("TG_API_ID")
    api_hash = get_parser_setting_str("TG_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("Задайте TG_API_ID и TG_API_HASH в настройках парсера.")
    try:
        api_id_int = int(api_id)
    except ValueError:
        raise RuntimeError("TG_API_ID должен быть числом.")
    proxy = _get_proxy()
    client = TelegramClient(StringSession(), api_id_int, api_hash, proxy=proxy)
    await client.connect()
    if not await client.is_user_authorized():
        sent = await client.send_code_request(phone)
        phone_code_hash = getattr(sent, "phone_code_hash", None)
        if not phone_code_hash:
            await client.disconnect()
            raise RuntimeError("Не удалось отправить код (неверный номер или лимиты Telegram).")
        _pending["client"] = client
        _pending["phone"] = phone
        _pending["phone_code_hash"] = phone_code_hash
    else:
        session_str = client.session.save()
        await client.disconnect()
        set_parser_setting("TG_SESSION_STRING", session_str)
        raise RuntimeError("Сессия уже авторизована и сохранена.")


async def submit_code(code: str, password: str | None = None) -> None:
    """
    Ввести код (и при необходимости пароль 2FA). Сессия сохраняется в настройки парсера.
    """
    global _pending
    if not _pending:
        raise RuntimeError("Сначала запросите код (укажите номер и нажмите «Запросить код»).")
    code = (code or "").strip()
    if not code:
        raise RuntimeError("Введите код из Telegram.")
    client = _pending["client"]
    phone = _pending["phone"]
    phone_code_hash = _pending["phone_code_hash"]
    try:
        try:
            await client.sign_in(
                phone,
                code=code,
                phone_code_hash=phone_code_hash,
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "password" in err_msg or "2fa" in err_msg or "two" in err_msg or "sessionpasswordneeded" in err_msg:
                if not (password or "").strip():
                    raise RuntimeError("Включена двухфакторная аутентификация. Введите пароль 2FA.") from e
                await client.sign_in(password=password.strip())
            else:
                raise
        session_str = client.session.save()
        set_parser_setting("TG_SESSION_STRING", session_str)
    finally:
        await client.disconnect()
        _pending.clear()


def has_pending() -> bool:
    return bool(_pending)
