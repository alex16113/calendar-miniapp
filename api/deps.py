"""
FastAPI dependencies для API Mini App (initData, user_id, admin).
"""
from __future__ import annotations

import logging
from fastapi import Header, HTTPException, Depends

from api.telegram_webapp import validate_init_data, get_user_id_from_validated

logger = logging.getLogger(__name__)


def get_telegram_user_id(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
) -> int:
    """
    Зависимость: проверяет initData из заголовка, возвращает user_id.
    При невалидных или отсутствующих данных — 401.
    
    DEV MODE: если env DISABLE_INIT_DATA_CHECK=1, возвращает ADMIN_ID без проверки.
    """
    import os
    from config import load_settings
    settings = load_settings()
    
    # DEV MODE: отключить проверку для диагностики (ТОЛЬКО ДЛЯ ОТЛАДКИ!)
    if os.environ.get("DISABLE_INIT_DATA_CHECK", "").strip() in ("1", "true", "yes"):
        logger.warning("DISABLE_INIT_DATA_CHECK=1: returning admin_id without validation (DEV MODE)")
        return settings.admin_id
    
    # DEBUG: логируем первые 50 символов initData для диагностики
    init_data_preview = x_telegram_init_data[:50] if x_telegram_init_data else "(empty)"
    logger.debug(f"Validating initData (preview): {init_data_preview}...")
    
    # Увеличенный TTL для диагностики (7 дней вместо 24 часов)
    # Если проблема в устаревшем auth_date - это поможет
    max_age = int(os.environ.get("INIT_DATA_MAX_AGE_SECONDS", str(7 * 24 * 3600)))
    logger.debug(f"Using max_auth_age_seconds: {max_age}")
    
    validated = validate_init_data(x_telegram_init_data, settings.bot_token, max_auth_age_seconds=max_age)
    if not validated:
        logger.warning(f"initData validation failed for data starting with: {init_data_preview}")
        raise HTTPException(status_code=401, detail="Invalid or expired init data")
    user_id = get_user_id_from_validated(validated)
    if user_id is None:
        logger.warning("user_id extraction failed from validated data")
        raise HTTPException(status_code=401, detail="User data missing in init data")
    
    logger.debug(f"Successfully validated user_id={user_id}")
    return user_id


def get_telegram_admin_id(
    user_id: int = Depends(get_telegram_user_id),
) -> int:
    """
    Зависимость для админ-эндпоинтов: проверяет, что user_id == ADMIN_ID.
    При несовпадении — 403.
    """
    from config import load_settings
    settings = load_settings()
    if user_id != settings.admin_id:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id
