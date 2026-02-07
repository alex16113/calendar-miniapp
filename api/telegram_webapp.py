"""
Валидация initData Telegram WebApp по документации:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)

# Максимальный возраст initData в секундах (защита от replay)
DEFAULT_MAX_AUTH_AGE_SECONDS = 86400  # 24 часа


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_auth_age_seconds: int = DEFAULT_MAX_AUTH_AGE_SECONDS,
) -> dict | None:
    """
    Проверяет подпись initData и возвращает распарсенные данные при успехе.

    init_data: строка из Telegram.WebApp.initData (query string).
    bot_token: токен бота.
    max_auth_age_seconds: если > 0, проверяем auth_date не старше N секунд.

    Returns:
        Словарь с ключами из initData (user — уже распарсенный объект с id, first_name и т.д.),
        либо None при невалидных данных.
    """
    if not init_data or not init_data.strip():
        logger.debug("initData is empty or whitespace")
        return None

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True)
    except Exception:
        logger.debug("initData parse_qsl failed", exc_info=True)
        return None

    params = dict(pairs)
    received_hash = params.pop("hash", None)
    if not received_hash:
        logger.debug("No hash field in initData")
        return None

    # data_check_string: все поля кроме hash, отсортированы по ключу, key=value через \n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )

    # secret_key = HMAC_SHA256(bot_token, "WebAppData")
    secret_key = hmac.new(
        bot_token.encode(),
        b"WebAppData",
        hashlib.sha256,
    ).digest()

    # computed_hash = HMAC_SHA256(secret_key, data_check_string), hex
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        logger.debug(f"HMAC mismatch: computed={computed_hash[:16]}..., received={received_hash[:16]}...")
        return None

    # Опционально: проверка возраста auth_date
    if max_auth_age_seconds > 0:
        auth_date_str = params.get("auth_date")
        if not auth_date_str:
            return None
        try:
            auth_date = int(auth_date_str)
        except ValueError:
            return None
        import time
        if int(time.time()) - auth_date > max_auth_age_seconds:
            logger.debug("initData auth_date too old")
            return None

    # Парсим user (JSON) для удобства
    user_json = params.get("user")
    if user_json:
        try:
            params["user"] = json.loads(user_json)
        except json.JSONDecodeError:
            pass

    return params


def get_user_id_from_validated(validated: dict) -> int | None:
    """Из уже валидированного initData извлекает user_id."""
    user = validated.get("user")
    if not user or not isinstance(user, dict):
        return None
    uid = user.get("id")
    if uid is None:
        return None
    try:
        return int(uid)
    except (TypeError, ValueError):
        return None
