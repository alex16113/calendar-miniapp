"""
FastAPI-приложение: API для Mini App и запуск бота в одном процессе.

Бот работает в фоне (asyncio task); при остановке uvicorn задача отменяется.
Раздаёт статику Mini App из dist/ (SPA fallback на index.html).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.deps import get_telegram_user_id
from api.admin import router as admin_router
from api.slots_service import (
    get_week_slots,
    get_day_slots,
    check_slot_available,
)

logger = logging.getLogger(__name__)

# Корень проекта (родитель api/); dist — результат сборки mini-app
STATIC_DIR = Path(__file__).resolve().parent.parent / "dist"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_DURATIONS = (15, 30, 60, 90)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск бота в фоне при старте, отмена при остановке. SKIP_BOT=1 — только API, без бота (для проверки сервера)."""
    bot_task = None
    if os.environ.get("SKIP_BOT", "").strip().lower() in ("1", "true", "yes"):
        logger.info("SKIP_BOT=1: bot disabled, only API + static")
    else:
        from bot import main as run_bot
        bot_task = asyncio.create_task(run_bot())
        logger.info("Bot task started in background")
    try:
        yield
    finally:
        if bot_task is not None:
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
            logger.info("Bot task stopped")


app = FastAPI(
    title="Calendar Mini App API",
    description="Backend для Telegram Mini App (слоты, бронирование, мои заявки)",
    lifespan=lifespan,
)

# CORS для Mini App: домен деплоя и Telegram origins (включая mobile apps)
# Telegram WebView в iOS/Android может использовать разные origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://calendar.vpncfo.ru",
        "https://web.telegram.org",
    ],
    allow_origin_regex=r"https://.*\.telegram\.org",  # Все поддомены Telegram
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)


@app.get("/health")
async def health():
    """Проверка живости сервиса (для прокси/деплоя)."""
    return {"status": "ok"}


@app.get("/me")
async def me(user_id: int = Depends(get_telegram_user_id)):
    """
    Тестовый эндпоинт: возвращает user_id из валидного initData.
    Заголовок: X-Telegram-Init-Data (строка из Telegram.WebApp.initData).
    """
    return {"user_id": user_id}


# --- Slots ---


@app.get("/slots/week")
async def slots_week(
    user_id: int = Depends(get_telegram_user_id),
    week_offset: int = Query(0, ge=0, description="Неделя: 0 = текущая, 1 = следующая"),
    duration: int = Query(30, description="Длительность встречи в минутах"),
):
    """Неделя с флагами has_slots по дням (понедельник — воскресенье)."""
    if duration not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail=f"duration must be one of {ALLOWED_DURATIONS}")
    days = await get_week_slots(week_offset=week_offset, duration_minutes=duration)
    week_start = days[0]["date"] if days else None
    return {"week_start": week_start, "days": days}


@app.get("/slots/day")
async def slots_day(
    user_id: int = Depends(get_telegram_user_id),
    date: str = Query(..., description="Дата YYYY-MM-DD", alias="date"),
    duration: int = Query(30, description="Длительность в минутах"),
):
    """Список слотов на день (время в таймзоне настроек), формат HH:MM."""
    if duration not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail=f"duration must be one of {ALLOWED_DURATIONS}")
    slots = await get_day_slots(date_str=date, duration_minutes=duration)
    return {"date": date, "slots": slots}


# --- Booking ---


class BookingBody(BaseModel):
    duration_minutes: int = Field(..., ge=15, le=90)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(..., pattern=r"^\d{1,2}:\d{2}$")  # HH:MM
    name: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    email: str = Field(..., min_length=1, max_length=254)


def _is_valid_email(email: str) -> bool:
    return bool(email and len(email) <= 254 and EMAIL_RE.match(email))


@app.post("/booking")
async def booking(
    body: BookingBody,
    user_id: int = Depends(get_telegram_user_id),
):
    """
    Создать заявку (pending). Требует валидный initData.
    После создания — уведомление админу в чат (без кнопок; модерация в Mini App).
    """
    if body.duration_minutes not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail=f"duration_minutes must be one of {ALLOWED_DURATIONS}")
    if not _is_valid_email(body.email):
        raise HTTPException(status_code=400, detail="Invalid email")

    from database import get_db
    from app_context import get_settings
    from services.meeting_formatter import format_admin_new_request

    db = get_db()
    if db.is_user_blacklisted(user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    available = await check_slot_available(
        date_str=body.date,
        time_str=body.time,
        duration_minutes=body.duration_minutes,
    )
    if not available:
        raise HTTPException(status_code=409, detail="Slot no longer available")

    settings = get_settings()
    tz_name = db.get_timezone()
    start_naive = datetime.strptime(f"{body.date}T{body.time}", "%Y-%m-%dT%H:%M")

    meeting_id = db.create_meeting(
        user_id=user_id,
        username=None,
        user_name=body.name.strip(),
        user_email=body.email.strip(),
        subject=body.subject.strip(),
        description=(body.description or "").strip() or None,
        start_time=start_naive,
        duration_minutes=body.duration_minutes,
        status="pending",
        timezone_name=tz_name,
    )
    logger.info("Meeting created via API", extra={"meeting_id": meeting_id, "user_id": user_id})

    meeting = db.get_meeting(meeting_id)
    if meeting:
        from handlers.moderation import moderation_kb
        text = format_admin_new_request(meeting, tz_name=tz_name)
        try:
            from aiogram import Bot
            bot = Bot(token=settings.bot_token)
            await bot.send_message(
                settings.admin_id,
                text,
                reply_markup=moderation_kb(meeting_id),
            )
            await bot.session.close()
        except Exception:
            logger.exception("Failed to notify admin", extra={"meeting_id": meeting_id})

    return {"meeting_id": meeting_id}


# --- Мои заявки ---

MY_MEETINGS_STATUSES = ("pending", "confirmed")
MY_MEETINGS_PAGE_SIZE = 10
MY_MEETINGS_PAGE_SIZE_MAX = 50


@app.get("/my/meetings")
async def my_meetings(
    user_id: int = Depends(get_telegram_user_id),
    page: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Список заявок пользователя (pending + confirmed) с пагинацией.
    """
    from database import get_db
    from services.meeting_formatter import format_local_datetime

    db = get_db()
    total = db.count_user_meetings(user_id=user_id, statuses=MY_MEETINGS_STATUSES)
    total_pages = max(1, (total + limit - 1) // limit)
    page_i = min(max(0, page), total_pages - 1)
    offset = page_i * limit
    meetings = db.list_user_meetings(
        user_id=user_id,
        statuses=MY_MEETINGS_STATUSES,
        limit=limit,
        offset=offset,
    )
    tz_name = db.get_timezone()
    items = []
    for m in meetings:
        start_utc = m.start_time
        if start_utc.tzinfo is None:
            from datetime import timezone as tz
            start_utc = start_utc.replace(tzinfo=tz.utc)
        items.append({
            "id": m.id,
            "status": m.status,
            "start_time_utc": start_utc.isoformat(),
            "start_local": format_local_datetime(start_utc, tz_name),
            "subject": (m.subject or "").strip() or None,
            "duration": m.duration,
            "google_event_html_link": m.google_event_html_link if m.status == "confirmed" else None,
        })
    return {
        "total": total,
        "page": page_i,
        "limit": limit,
        "total_pages": total_pages,
        "items": items,
    }


@app.post("/my/meetings/{meeting_id}/cancel")
async def my_meetings_cancel(
    meeting_id: int,
    user_id: int = Depends(get_telegram_user_id),
):
    """
    Отмена своей pending-заявки. Только если заявка принадлежит user_id и status=pending.
    """
    from database import get_db

    db = get_db()
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your meeting")
    if meeting.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending meetings can be cancelled")
    updated = db.update_meeting_status_if_current(
        meeting_id, from_status="pending", to_status="cancelled"
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Meeting already changed status")
    return {"ok": True}


# Middleware для добавления заголовков безопасности (только для статики)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        # Для HTML и JS файлов — разрешаем inline scripts (нужно для Telegram SDK)
        if request.url.path.endswith(('.html', '.js')) or request.url.path == '/':
            # Разрешаем Telegram origins и inline scripts
            response.headers['X-Frame-Options'] = 'ALLOW-FROM https://web.telegram.org'
            # Не ставим строгий CSP — он может блокировать Telegram SDK
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Раздача статики Mini App (сборка из mini-app/dist). SPA (HashRouter) — fallback на index.html
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    logger.info("Serving Mini App static from %s", STATIC_DIR)
else:
    logger.warning("Static dir %s not found; Mini App will not be served at /", STATIC_DIR)
