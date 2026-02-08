from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app_context import get_settings


logger = logging.getLogger(__name__)
router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    logger.info("Command /start", extra={"user_id": message.from_user.id if message.from_user else None})
    s = get_settings()
    is_admin = bool(message.from_user and message.from_user.id == s.admin_id)
    text = (
        "Привет, это ассистент Алексея.\n"
        "Я помогу тебе подобрать слот на встречу с ним.\n\n"
        "Команды:\n"
        "/help\n"
    )
    if is_admin:
        text += "/admin (только для владельца)\n"
    text += "/my (мои заявки)\n"
    text += "/book (записаться)\n\n"
    text += "Нажми кнопку, чтобы начать запись."
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    logger.info("Command /help", extra={"user_id": message.from_user.id if message.from_user else None})
    s = get_settings()
    is_admin = bool(message.from_user and message.from_user.id == s.admin_id)
    text = "Пока доступно:\n- /start\n- /help\n"
    if is_admin:
        text += "- /admin (для админа)\n"
    text += "- /my (мои заявки)\n"
    text += "\nСледующий шаг — пошаговая запись на встречу."
    await message.answer(text)

