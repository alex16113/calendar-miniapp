"""
FastAPI dependencies для API Mini App (initData, user_id, admin).
"""
from __future__ import annotations

from fastapi import Header, HTTPException, Depends

from api.telegram_webapp import validate_init_data, get_user_id_from_validated


def get_telegram_user_id(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
) -> int:
    """
    Зависимость: проверяет initData из заголовка, возвращает user_id.
    При невалидных или отсутствующих данных — 401.
    """
    from config import load_settings
    settings = load_settings()
    validated = validate_init_data(x_telegram_init_data, settings.bot_token)
    if not validated:
        raise HTTPException(status_code=401, detail="Invalid or expired init data")
    user_id = get_user_id_from_validated(validated)
    if user_id is None:
        raise HTTPException(status_code=401, detail="User data missing in init data")
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
