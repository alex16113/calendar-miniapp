from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from datetime import timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage

from config import load_settings
from database import init_db
from handlers import booking_router, common_router, moderation_router, my_requests_router, setup_admin_router
from logging_setup import setup_logging
from middlewares.log_context import LogContextMiddleware
from services.google_calendar_service import GoogleCalendarService
from services.meeting_formatter import format_user_expired


logger = logging.getLogger(__name__)


def _acquire_lock() -> object | None:
    """
    Защита от запуска нескольких экземпляров polling одновременно.
    """
    import fcntl

    runtime_dir = Path(__file__).resolve().parent / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_path = runtime_dir / "bot.lock"

    f = open(lock_path, "w")
    expire_task: asyncio.Task[None] | None = None
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        return None

    f.write(str(os.getpid()))
    f.flush()
    return f  # держим дескриптор открытым, чтобы не потерять lock


async def _expire_pending_loop(bot: Bot, *, ttl_hours: int, interval_seconds: int) -> None:
    """
    Фоновая задача: переводит старые pending в expired и уведомляет пользователя.
    """
    from database import get_db

    db = get_db()
    while True:
        try:
            expired = await asyncio.to_thread(db.expire_old_pending_with_list, ttl_hours)
            if expired:
                tz_name = db.get_timezone()
                for m in expired:
                    try:
                        await bot.send_message(
                            m.user_id,
                            format_user_expired(m, tz_name=tz_name),
                        )
                    except Exception:
                        logger.exception("Failed to notify user about expired meeting", extra={"meeting_id": m.id, "user_id": m.user_id})
        except Exception:
            logger.exception("Expire pending loop failed")

        await asyncio.sleep(max(5, int(interval_seconds)))


async def main() -> None:
    setup_logging()
    settings = load_settings()

    logger.info("Starting bot")

    if settings.google_auth_mode == "oauth":
        oauth = GoogleCalendarService(
            client_secrets_path=settings.oauth_client_secrets_path,
            token_path=settings.oauth_token_path,
        )
        url = oauth.try_print_auth_hint()
        if url:
            # Требование ТЗ: если токена нет — печатаем ссылку на авторизацию в терминал при запуске.
            print("\nGoogle OAuth требуется для Calendar/Meet.\nОткрой ссылку и авторизуйся, затем создай token.json:")
            print(url)
            print("После авторизации можно запустить: python scripts/google_oauth_init.py\n")

    lock = _acquire_lock()
    if lock is None:
        logger.error("Another bot instance is already running; exiting")
        return

    # Инициализация БД + дефолтные настройки (не перетирает существующие).
    db = init_db(settings.db_path)
    db.bootstrap_settings(
        timezone=settings.timezone,
        work_start=settings.work_start,
        work_end=settings.work_end,
        buffer_hours=settings.buffer_hours,
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    expire_task: asyncio.Task[None] | None = None
    try:
        try:
            me = await bot.get_me()
            logger.info("Authorized as bot", extra={"bot_id": me.id, "bot_username": me.username})
        except TelegramUnauthorizedError:
            logger.error("BOT_TOKEN invalid: Telegram returned Unauthorized")
            return

        # На случай если ранее был включён webhook (иначе polling не получит апдейты).
        await bot.delete_webhook(drop_pending_updates=False)

        dp = Dispatcher(storage=MemoryStorage())
        dp.update.middleware(LogContextMiddleware())

        dp.include_router(common_router)
        # Важно: админ-команды должны “перебивать” FSM пользователя (иначе /admin может
        # быть съеден state-хендлерами booking).
        dp.include_router(setup_admin_router(settings))
        dp.include_router(my_requests_router)
        dp.include_router(booking_router)
        dp.include_router(moderation_router)

        expire_task = asyncio.create_task(
            _expire_pending_loop(
                bot,
                ttl_hours=settings.pending_ttl_hours,
                interval_seconds=settings.expire_check_interval_seconds,
            )
        )

        await dp.start_polling(bot)
    finally:
        if expire_task is not None:
            expire_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

