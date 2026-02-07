"""
Валидация initData Telegram WebApp.

Поддерживает ДВА формата:
1. Старый (hash) — HMAC-SHA256 с bot_token
   https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
2. Новый (signature) — Ed25519 с публичным ключом Telegram
   https://docs.telegram-mini-apps.com/platform/init-data#using-telegram-public-key
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

logger = logging.getLogger(__name__)

# Максимальный возраст initData в секундах (защита от replay)
DEFAULT_MAX_AUTH_AGE_SECONDS = 86400  # 24 часа

# Ed25519 публичные ключи Telegram для верификации signature
# https://docs.telegram-mini-apps.com/platform/init-data#using-telegram-public-key
TELEGRAM_ED25519_PUBLIC_KEY_PROD = "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d"
TELEGRAM_ED25519_PUBLIC_KEY_TEST = "40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec"


def _validate_via_hmac(data_check_string: str, bot_token: str, received_hash: str) -> bool:
    """Старый метод: HMAC-SHA256 валидация (поле hash)."""
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256,
    ).digest()

    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    if hmac.compare_digest(computed_hash, received_hash):
        logger.debug("HMAC validation SUCCESS")
        return True

    logger.debug(f"HMAC mismatch: computed={computed_hash[:16]}..., received={received_hash[:16]}...")
    return False


def _validate_via_ed25519(data_check_string: str, bot_token: str, signature_b64: str) -> bool:
    """
    Новый метод: Ed25519 валидация (поле signature).
    
    Алгоритм:
    1. data_check_string уже содержит отсортированные key=value (без hash и signature)
    2. Строим: "{bot_id}:WebAppData\n{data_check_string}"
    3. Верифицируем Ed25519 подпись
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        logger.error("cryptography package not installed — cannot verify Ed25519 signature")
        return False

    # Извлекаем bot_id из bot_token (формат: "123456:ABCdef...")
    bot_id = bot_token.split(":")[0]
    
    # Формируем строку для верификации: "{bot_id}:WebAppData\n{data_check_string}"
    verify_string = f"{bot_id}:WebAppData\n{data_check_string}"
    
    logger.debug(f"Ed25519 verify_string preview: {verify_string[:80]}...")
    
    # Декодируем signature из base64url
    # Telegram может отправлять без padding — добавляем
    sig_padded = signature_b64 + "=" * (4 - len(signature_b64) % 4) if len(signature_b64) % 4 else signature_b64
    try:
        signature_bytes = base64.urlsafe_b64decode(sig_padded)
    except Exception:
        logger.warning(f"Failed to decode signature from base64url")
        return False
    
    logger.debug(f"Signature decoded: {len(signature_bytes)} bytes")
    
    # Загружаем публичный ключ Telegram (production)
    try:
        public_key_bytes = bytes.fromhex(TELEGRAM_ED25519_PUBLIC_KEY_PROD)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except Exception:
        logger.error("Failed to load Telegram Ed25519 public key")
        return False
    
    # Верифицируем подпись
    try:
        public_key.verify(signature_bytes, verify_string.encode())
        logger.debug("Ed25519 signature verification SUCCESS")
        return True
    except Exception:
        logger.debug("Ed25519 signature verification FAILED with production key, trying test key...")
    
    # Пробуем test key
    try:
        test_key_bytes = bytes.fromhex(TELEGRAM_ED25519_PUBLIC_KEY_TEST)
        test_key = Ed25519PublicKey.from_public_bytes(test_key_bytes)
        test_key.verify(signature_bytes, verify_string.encode())
        logger.debug("Ed25519 signature verification SUCCESS (test key)")
        return True
    except Exception:
        logger.warning("Ed25519 signature verification FAILED with both keys")
        return False


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_auth_age_seconds: int = DEFAULT_MAX_AUTH_AGE_SECONDS,
) -> dict | None:
    """
    Проверяет подпись initData и возвращает распарсенные данные при успехе.
    
    Поддерживает два формата:
    - hash (HMAC-SHA256) — старый формат
    - signature (Ed25519) — новый формат (Bot API 8.0+)
    """
    logger.debug(f"validate_init_data called, data length: {len(init_data) if init_data else 0}")

    if not init_data or not init_data.strip():
        logger.debug("initData is empty or whitespace")
        return None

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True)
    except Exception:
        logger.debug("initData parse_qsl failed", exc_info=True)
        return None

    params = dict(pairs)
    
    # Определяем формат: hash (старый) или signature (новый)
    received_hash = params.pop("hash", None)
    received_signature = params.pop("signature", None)
    
    use_ed25519 = received_signature is not None and received_hash is None
    
    logger.debug(f"Validation mode: {'Ed25519 (signature)' if use_ed25519 else 'HMAC (hash)'}")
    logger.debug(f"Params keys: {list(params.keys())}")

    # Строим data_check_string: исключаем hash и signature, сортируем по ключу
    filtered_params = {k: v for k, v in params.items() if k not in ("hash", "signature")}
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(filtered_params.items())
    )
    logger.debug(f"data_check_string preview: {data_check_string[:100]}...")

    # Валидация
    if use_ed25519:
        # Новый формат: Ed25519
        valid = _validate_via_ed25519(data_check_string, bot_token, received_signature)
    else:
        if not received_hash:
            logger.debug("No hash or signature field in initData")
            return None
        # Старый формат: HMAC-SHA256
        valid = _validate_via_hmac(data_check_string, bot_token, received_hash)
    
    if not valid:
        return None

    # Проверка возраста auth_date
    if max_auth_age_seconds > 0:
        auth_date_str = filtered_params.get("auth_date")
        if not auth_date_str:
            logger.warning("No auth_date in initData")
            return None
        try:
            auth_date = int(auth_date_str)
        except ValueError:
            logger.warning(f"Invalid auth_date format: {auth_date_str}")
            return None
        current_time = int(time.time())
        age_seconds = current_time - auth_date
        logger.debug(f"auth_date age: {age_seconds}s (max: {max_auth_age_seconds}s)")
        if age_seconds > max_auth_age_seconds:
            logger.warning(f"initData auth_date too old: {age_seconds}s > {max_auth_age_seconds}s")
            return None

    # Парсим user (JSON) для удобства
    result = dict(filtered_params)
    user_json = result.get("user")
    if user_json:
        try:
            result["user"] = json.loads(user_json)
            logger.debug(f"Parsed user: id={result['user'].get('id')}")
        except json.JSONDecodeError:
            logger.warning("Failed to parse user JSON")

    logger.debug("initData validation SUCCESS")
    return result


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
