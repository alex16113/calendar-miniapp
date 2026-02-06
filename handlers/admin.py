from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Settings
from database import get_db
from handlers.states import AdminFSM
from services.google_api import get_calendar_timezone
from handlers.moderation import moderation_kb


logger = logging.getLogger(__name__)
router = Router(name="admin")

PENDING_PAGE_SIZE = 5


def _is_admin_id(user_id: int, settings: Settings) -> bool:
    return user_id == settings.admin_id


def _is_admin_message(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and _is_admin_id(message.from_user.id, settings))


def _is_admin_callback(call: CallbackQuery, settings: Settings) -> bool:
    return bool(call.from_user and _is_admin_id(call.from_user.id, settings))

def _parse_hhmm(value: str) -> time:
    s = value.strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError
    h = int(parts[0])
    m = int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError
    return time(hour=h, minute=m)

WEEKDAYS_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


def _admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🌍 Таймзона", callback_data="admin:tz"))
    kb.row(InlineKeyboardButton(text="🕒 Рабочие часы", callback_data="admin:wh"))
    kb.row(InlineKeyboardButton(text="⏳ Буфер (часы)", callback_data="admin:buf"))
    kb.row(InlineKeyboardButton(text="🚫 Blacklist дат", callback_data="admin:bl"))
    kb.row(InlineKeyboardButton(text="🗂️ Список ожидания (pending)", callback_data="admin:pending"))
    kb.row(InlineKeyboardButton(text="📣 Broadcast", callback_data="admin:bc"))
    return kb.as_markup()

def _tz_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🗓️ Взять из Google Calendar", callback_data="admin:tz:google"))
    kb.row(InlineKeyboardButton(text="Москва (MSK)", callback_data="admin:tz:set:Europe/Moscow"))
    kb.row(InlineKeyboardButton(text="Калининград", callback_data="admin:tz:set:Europe/Kaliningrad"))
    kb.row(InlineKeyboardButton(text="Екатеринбург", callback_data="admin:tz:set:Asia/Yekaterinburg"))
    kb.row(InlineKeyboardButton(text="Новосибирск", callback_data="admin:tz:set:Asia/Novosibirsk"))
    kb.row(InlineKeyboardButton(text="Иркутск", callback_data="admin:tz:set:Asia/Irkutsk"))
    kb.row(InlineKeyboardButton(text="Якутск", callback_data="admin:tz:set:Asia/Yakutsk"))
    kb.row(InlineKeyboardButton(text="Владивосток", callback_data="admin:tz:set:Asia/Vladivostok"))
    kb.row(InlineKeyboardButton(text="✍️ Другая…", callback_data="admin:tz:custom"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu"))
    return kb.as_markup()


def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")]])


def _blacklist_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📋 Показать список", callback_data="admin:bl:list"))
    kb.row(InlineKeyboardButton(text="➕ Добавить дату", callback_data="admin:bl:add"))
    kb.row(InlineKeyboardButton(text="➖ Удалить дату", callback_data="admin:bl:remove"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu"))
    return kb.as_markup()

def _workdays_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, name in enumerate(WEEKDAYS_RU):
        kb.button(text=name, callback_data=f"admin:wh:day:{i}")
    kb.adjust(4, 3)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu"))
    return kb.as_markup()


def _workday_actions_kb(weekday: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🕒 Задать часы", callback_data=f"admin:wh:set:{weekday}"))
    kb.row(InlineKeyboardButton(text="🏖️ Выходной", callback_data=f"admin:wh:off:{weekday}"))
    kb.row(InlineKeyboardButton(text="⬅️ Назад к дням", callback_data="admin:wh"))
    return kb.as_markup()


async def _render_admin_status(message: Message) -> None:
    db = get_db()
    tz = db.get_timezone()
    work_start, work_end = db.get_work_hours()
    buffer_hours = db.get_buffer_hours()
    await message.answer(
        "Админ-панель\n\n"
        f"Таймзона: {tz}\n"
        f"Рабочие часы: {work_start}–{work_end}\n"
        f"Буфер: {buffer_hours} ч\n\n"
        "Выбери, что изменить:",
        reply_markup=_admin_menu_kb(),
    )

def _format_local(dt_utc: datetime, tz_name: str) -> str:
    tz = pytz.timezone(tz_name)
    return dt_utc.astimezone(timezone.utc).astimezone(tz).strftime("%d.%m.%Y %H:%M")


def _pending_list_text(meetings: list, *, tz_name: str, page: int, total: int, total_pages: int) -> str:
    header = f"🗂️ Pending-заявки: {total}\nСтраница: {page+1}/{max(1,total_pages)}\n"
    if not meetings:
        return header + "\nПусто."
    lines = []
    for m in meetings:
        when = _format_local(m.start_time, tz_name)
        name = (m.user_name or "").strip() or "(без имени)"
        subject = (m.subject or "").strip() or "(без темы)"
        email = (m.user_email or "").strip() or "(без email)"
        lines.append(f"#{m.id} | {when} | {m.duration} мин | {name} | {email} | {subject}")
    return header + "\n" + "\n".join(lines)


def _pending_list_kb(meetings: list, *, page: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for m in meetings:
        mid = int(m.id or 0)
        if mid <= 0:
            continue
        kb.row(
            InlineKeyboardButton(text=f"✅ {mid}", callback_data=f"meet:confirm:{mid}"),
            InlineKeyboardButton(text=f"❌ {mid}", callback_data=f"meet:reject:{mid}"),
            InlineKeyboardButton(text=f"🚫 {mid}", callback_data=f"meet:ban:{mid}"),
            InlineKeyboardButton(text="📄", callback_data=f"admin:pending:open:{mid}:{page}"),
        )

    total_pages = max(1, (int(total) + PENDING_PAGE_SIZE - 1) // PENDING_PAGE_SIZE)
    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="⬅️", callback_data=f"admin:pending:page:{page-1}")
    if page + 1 < total_pages:
        nav.button(text="➡️", callback_data=f"admin:pending:page:{page+1}")
    nav.button(text="🔄", callback_data=f"admin:pending:page:{page}")
    nav.adjust(3)
    kb.attach(nav)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu"))
    return kb.as_markup()


def _pending_details_kb(meeting_id: int, *, page: int) -> InlineKeyboardMarkup:
    # быстрые действия + возврат к списку
    base = moderation_kb(meeting_id)
    kb = InlineKeyboardBuilder()
    # moderation_kb уже строит разметку, но нам нужно добавить кнопку назад
    for row in base.inline_keyboard:
        kb.row(*row)
    kb.row(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data=f"admin:pending:page:{page}"))
    kb.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="admin:menu"))
    return kb.as_markup()


def _broadcast_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Отправить", callback_data="admin:bc:send"))
    kb.row(InlineKeyboardButton(text="Отмена", callback_data="admin:cancel"))
    return kb.as_markup()


def setup_admin_router(settings: Settings) -> Router:
    """
    Подкладываем settings в замыкание хендлеров без DI на первом этапе.
    """

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            logger.warning(
                "Admin access denied",
                extra={"user_id": message.from_user.id if message.from_user else None},
            )
            await message.answer("Нет доступа.")
            return

        logger.info("Admin panel opened", extra={"admin_id": settings.admin_id})
        await state.clear()
        await _render_admin_status(message)

    @router.callback_query(F.data == "admin:menu")
    async def cb_admin_menu(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.clear()
        await call.message.answer("Ок.", reply_markup=None)
        await _render_admin_status(call.message)
        await call.answer()

    @router.callback_query(F.data == "admin:cancel")
    async def cb_admin_cancel(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.clear()
        await call.message.answer("Ок, отменил.", reply_markup=None)
        await _render_admin_status(call.message)
        await call.answer()

    # --- pending list ---
    async def _show_pending_page(call: CallbackQuery, state: FSMContext, *, page: int) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return

        try:
            db = get_db()
            total = db.count_pending_meetings()
            total_pages = max(1, (int(total) + PENDING_PAGE_SIZE - 1) // PENDING_PAGE_SIZE)
            page_i = max(0, min(int(page), total_pages - 1))
            offset = page_i * PENDING_PAGE_SIZE
            meetings = db.list_pending_meetings(limit=PENDING_PAGE_SIZE, offset=offset)
            tz_name = db.get_timezone()

            await state.clear()
            await call.message.edit_text(
                _pending_list_text(meetings, tz_name=tz_name, page=page_i, total=total, total_pages=total_pages),
                reply_markup=_pending_list_kb(meetings, page=page_i, total=total),
            )
            await call.answer()
        except Exception:
            logger.exception("Failed to render pending list", extra={"admin_id": settings.admin_id, "page": page})
            await call.answer("Не смог открыть список. См. логи.", show_alert=True)

    @router.callback_query(F.data == "admin:pending")
    async def cb_admin_pending(call: CallbackQuery, state: FSMContext) -> None:
        await _show_pending_page(call, state, page=0)

    @router.callback_query(F.data.startswith("admin:pending:page:"))
    async def cb_admin_pending_page(call: CallbackQuery, state: FSMContext) -> None:
        try:
            page = int((call.data or "").split("admin:pending:page:", 1)[1])
        except Exception:
            await call.answer("Некорректно.", show_alert=True)
            return
        await _show_pending_page(call, state, page=page)

    @router.callback_query(F.data.startswith("admin:pending:open:"))
    async def cb_admin_pending_open(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return

        # admin:pending:open:{meeting_id}:{page}
        try:
            parts = (call.data or "").split(":")
            meeting_id = int(parts[3])
            page = int(parts[4]) if len(parts) > 4 else 0
        except Exception:
            await call.answer("Некорректно.", show_alert=True)
            return

        db = get_db()
        m = db.get_meeting(meeting_id)
        if m is None:
            await call.answer("Заявка не найдена.", show_alert=True)
            return
        if m.status != "pending":
            await call.answer(f"Уже обработано (status={m.status}).", show_alert=True)
            return

        tz_name = db.get_timezone()
        when = _format_local(m.start_time, tz_name)
        username = f"@{m.username}" if m.username else "(без username)"
        name = (m.user_name or "").strip() or "(без имени)"
        email = (m.user_email or "").strip() or "(без email)"
        subject = (m.subject or "").strip() or "(без темы)"
        description = (m.description or "").strip() or "отсутствует"

        await state.clear()
        await call.message.edit_text(
            "🔔 Pending заявка\n"
            f"👤 Имя: {name} ({username})\n"
            f"📧 Email: {email}\n"
            f"📝 Тема: {subject}\n"
            f"📄 Описание: {description}\n"
            f"⏰ Время: {when} ({m.duration} мин)\n"
            f"ID: {m.id}",
            reply_markup=_pending_details_kb(meeting_id, page=page),
        )
        await call.answer()

    # --- timezone ---
    @router.callback_query(F.data == "admin:tz")
    async def cb_admin_timezone(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.clear()
        await call.message.answer("Выбери таймзону:", reply_markup=_tz_menu_kb())
        await call.answer()

    @router.callback_query(F.data.startswith("admin:tz:set:"))
    async def cb_admin_tz_set(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return

        tz_name = (call.data or "").split("admin:tz:set:", 1)[1].strip()
        if not tz_name or tz_name not in pytz.all_timezones_set:
            await call.answer("Некорректная таймзона.", show_alert=True)
            return

        get_db().set_timezone(tz_name)
        logger.info("Timezone updated via admin (quick pick)", extra={"admin_id": settings.admin_id, "timezone": tz_name})
        await state.clear()
        await call.message.answer(f"Ок, таймзона: {tz_name}", reply_markup=None)
        await _render_admin_status(call.message)
        await call.answer()

    @router.callback_query(F.data == "admin:tz:custom")
    async def cb_admin_tz_custom(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.set_state(AdminFSM.timezone)
        await call.message.answer("Введи таймзону (например `Europe/Moscow`).", reply_markup=_cancel_kb())
        await call.answer()

    @router.callback_query(F.data == "admin:tz:google")
    async def cb_admin_tz_google(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        if not settings.calendar_id:
            await call.answer("CALENDAR_ID не задан.", show_alert=True)
            return
        try:
            tz_name = await asyncio.to_thread(
                get_calendar_timezone,
                calendar_id=settings.calendar_id,
                auth_mode=settings.google_auth_mode,
                service_account_json=settings.credentials_path,
                oauth_client_secrets_json=settings.oauth_client_secrets_path,
                oauth_token_json=settings.oauth_token_path,
            )
        except Exception:
            logger.exception("Failed to fetch timezone from Google Calendar")
            await call.answer("Не смог прочитать таймзону из Google Calendar.", show_alert=True)
            return
        if not tz_name or tz_name not in pytz.all_timezones_set:
            await call.answer("Google вернул странную таймзону.", show_alert=True)
            return

        get_db().set_timezone(tz_name)
        logger.info("Timezone updated via admin (google)", extra={"admin_id": settings.admin_id, "timezone": tz_name})
        await state.clear()
        await call.message.answer(f"Ок, таймзона из Google: {tz_name}", reply_markup=None)
        await _render_admin_status(call.message)
        await call.answer()

    @router.message(AdminFSM.timezone)
    async def st_admin_timezone(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        tz_name = (message.text or "").strip()
        if not tz_name or tz_name not in pytz.all_timezones_set:
            await message.answer("Некорректная таймзона. Пример: `Europe/Moscow`.", reply_markup=_cancel_kb())
            return
        get_db().set_timezone(tz_name)
        logger.info("Timezone updated via admin", extra={"admin_id": settings.admin_id, "timezone": tz_name})
        await state.clear()
        await message.answer(f"Ок, таймзона: {tz_name}")
        await _render_admin_status(message)

    # --- work hours ---
    @router.callback_query(F.data == "admin:wh")
    async def cb_admin_work_hours(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.clear()
        await call.message.answer("Выбери день недели:", reply_markup=_workdays_kb())
        await call.answer()

    @router.callback_query(F.data.startswith("admin:wh:day:"))
    async def cb_admin_workday_pick(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        try:
            weekday = int((call.data or "").split(":", 3)[3])
        except Exception:
            await call.answer("Некорректно.", show_alert=True)
            return
        if weekday < 0 or weekday > 6:
            await call.answer("Некорректно.", show_alert=True)
            return

        db = get_db()
        schedule = db.get_work_schedule()
        item = schedule.get(str(weekday)) or {}
        enabled = bool(item.get("enabled"))
        label = WEEKDAYS_RU[weekday]
        if enabled:
            start = str(item.get("start") or "")
            end = str(item.get("end") or "")
            text = f"{label}: {start}–{end}"
        else:
            text = f"{label}: выходной"

        await state.set_state(AdminFSM.work_hours_day)
        await state.update_data(workday_weekday=weekday)
        await call.message.answer(text, reply_markup=_workday_actions_kb(weekday))
        await call.answer()

    @router.callback_query(F.data.startswith("admin:wh:off:"))
    async def cb_admin_workday_off(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        try:
            weekday = int((call.data or "").split(":", 3)[3])
        except Exception:
            await call.answer("Некорректно.", show_alert=True)
            return
        get_db().set_work_schedule_day(weekday=weekday, enabled=False)
        logger.info("Workday set to off", extra={"admin_id": settings.admin_id, "weekday": weekday})
        await state.clear()
        await call.message.answer(f"Ок, {WEEKDAYS_RU[weekday]} — выходной.")
        await _render_admin_status(call.message)
        await call.answer()

    @router.callback_query(F.data.startswith("admin:wh:set:"))
    async def cb_admin_workday_set(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        try:
            weekday = int((call.data or "").split(":", 3)[3])
        except Exception:
            await call.answer("Некорректно.", show_alert=True)
            return
        await state.set_state(AdminFSM.work_hours)
        await state.update_data(workday_weekday=weekday)
        await call.message.answer(
            f"{WEEKDAYS_RU[weekday]}: введи часы в формате `HH:MM-HH:MM` (например `09:00-16:00`).",
            reply_markup=_cancel_kb(),
        )
        await call.answer()

    @router.message(AdminFSM.work_hours)
    async def st_admin_workday_hours(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        data = await state.get_data()
        weekday = int(data.get("workday_weekday", -1))
        if weekday < 0 or weekday > 6:
            await state.clear()
            await message.answer("Не понял день недели. Открой /admin заново.")
            return

        raw = (message.text or "").strip().replace("—", "-").replace("–", "-")
        if "-" not in raw:
            await message.answer("Нужен формат `HH:MM-HH:MM`.", reply_markup=_cancel_kb())
            return
        left, right = [p.strip() for p in raw.split("-", 1)]
        try:
            t0 = _parse_hhmm(left)
            t1 = _parse_hhmm(right)
        except Exception:
            await message.answer("Некорректное время. Формат: `09:00-16:00`.", reply_markup=_cancel_kb())
            return
        if t0 >= t1:
            await message.answer("Начало должно быть раньше конца.", reply_markup=_cancel_kb())
            return

        get_db().set_work_schedule_day(weekday=weekday, enabled=True, start=left, end=right)
        logger.info("Workday hours updated", extra={"admin_id": settings.admin_id, "weekday": weekday, "start": left, "end": right})
        await state.clear()
        await message.answer(f"Ок, {WEEKDAYS_RU[weekday]}: {left}–{right}")
        await _render_admin_status(message)

    # --- buffer ---
    @router.callback_query(F.data == "admin:buf")
    async def cb_admin_buffer(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.set_state(AdminFSM.buffer_hours)
        await call.message.answer("Введи буфер в часах (целое число, например `3`).", reply_markup=_cancel_kb())
        await call.answer()

    @router.message(AdminFSM.buffer_hours)
    async def st_admin_buffer(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        raw = (message.text or "").strip()
        try:
            v = int(raw)
        except Exception:
            await message.answer("Нужно целое число (например `3`).", reply_markup=_cancel_kb())
            return
        if v < 0 or v > 168:
            await message.answer("Странное значение. Введи 0..168.", reply_markup=_cancel_kb())
            return
        get_db().set_buffer_hours(v)
        logger.info("Buffer updated via admin", extra={"admin_id": settings.admin_id, "buffer_hours": v})
        await state.clear()
        await message.answer(f"Ок, буфер: {v} ч")
        await _render_admin_status(message)

    # --- blacklist ---
    @router.callback_query(F.data == "admin:bl")
    async def cb_admin_blacklist(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.clear()
        await call.message.answer("Blacklist дат:", reply_markup=_blacklist_menu_kb())
        await call.answer()

    @router.callback_query(F.data == "admin:bl:list")
    async def cb_admin_blacklist_list(call: CallbackQuery) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        items = get_db().list_blacklist_dates(limit=50)
        if not items:
            await call.message.answer("Blacklist пуст.", reply_markup=_blacklist_menu_kb())
            await call.answer()
            return
        lines = []
        for d, reason in items:
            lines.append(f"- {d}" + (f" — {reason}" if reason else ""))
        await call.message.answer("Blacklist (до 50):\n" + "\n".join(lines), reply_markup=_blacklist_menu_kb())
        await call.answer()

    @router.callback_query(F.data == "admin:bl:add")
    async def cb_admin_blacklist_add(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.set_state(AdminFSM.blacklist_add)
        await call.message.answer(
            "Введи дату `YYYY-MM-DD` и (опционально) причину.\n"
            "Пример: `2026-02-10 отпуск`",
            reply_markup=_cancel_kb(),
        )
        await call.answer()

    @router.message(AdminFSM.blacklist_add)
    async def st_admin_blacklist_add(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Нужна дата `YYYY-MM-DD`.", reply_markup=_cancel_kb())
            return
        parts = raw.split(maxsplit=1)
        date_s = parts[0]
        reason: Optional[str] = parts[1].strip() if len(parts) > 1 else None
        try:
            # validate format
            from datetime import date as _date

            _date.fromisoformat(date_s)
        except Exception:
            await message.answer("Некорректная дата. Формат: `YYYY-MM-DD`.", reply_markup=_cancel_kb())
            return
        get_db().add_blacklist_date(date_s, reason=reason)
        logger.info("Blacklist date added via admin", extra={"admin_id": settings.admin_id, "date": date_s})
        await state.clear()
        await message.answer(f"Ок, добавил {date_s}" + (f" — {reason}" if reason else ""))
        await message.answer("Blacklist дат:", reply_markup=_blacklist_menu_kb())

    @router.callback_query(F.data == "admin:bl:remove")
    async def cb_admin_blacklist_remove(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.set_state(AdminFSM.blacklist_remove)
        await call.message.answer("Введи дату `YYYY-MM-DD`, которую убрать из blacklist.", reply_markup=_cancel_kb())
        await call.answer()

    @router.message(AdminFSM.blacklist_remove)
    async def st_admin_blacklist_remove(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        date_s = (message.text or "").strip().split()[0] if (message.text or "").strip() else ""
        try:
            from datetime import date as _date

            _date.fromisoformat(date_s)
        except Exception:
            await message.answer("Некорректная дата. Формат: `YYYY-MM-DD`.", reply_markup=_cancel_kb())
            return
        removed = get_db().remove_blacklist_date(date_s)
        logger.info("Blacklist date removed via admin", extra={"admin_id": settings.admin_id, "date": date_s, "removed": removed})
        await state.clear()
        await message.answer("Ок, удалил." if removed else "Этой даты не было в blacklist.")
        await message.answer("Blacklist дат:", reply_markup=_blacklist_menu_kb())

    # --- broadcast ---
    @router.callback_query(F.data == "admin:bc")
    async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return
        await state.set_state(AdminFSM.broadcast_date)
        await call.message.answer("На какую дату рассылка? Введи `YYYY-MM-DD`.", reply_markup=_cancel_kb())
        await call.answer()

    @router.message(AdminFSM.broadcast_date)
    async def st_admin_broadcast_date(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        raw = (message.text or "").strip()
        try:
            d = date.fromisoformat(raw)
        except Exception:
            await message.answer("Некорректная дата. Формат: `YYYY-MM-DD`.", reply_markup=_cancel_kb())
            return

        db = get_db()
        tz_name = db.get_timezone()
        tz = pytz.timezone(tz_name)
        start_local = tz.localize(datetime.combine(d, time.min))
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)

        meetings = db.list_meetings_in_time_range(
            status="confirmed",
            start_time_min_utc=start_utc,
            start_time_max_utc=end_utc,
            limit=5000,
        )
        user_ids = sorted({m.user_id for m in meetings})

        await state.update_data(
            broadcast_date=d.isoformat(),
            broadcast_user_ids=user_ids,
        )
        await state.set_state(AdminFSM.broadcast_text)

        await message.answer(
            f"Ок, получателей: {len(user_ids)}.\n"
            "Теперь введи текст рассылки одним сообщением.",
            reply_markup=_cancel_kb(),
        )

    @router.message(AdminFSM.broadcast_text)
    async def st_admin_broadcast_text(message: Message, state: FSMContext) -> None:
        if not _is_admin_message(message, settings):
            await state.clear()
            return
        text = (message.text or "").strip()
        if not text:
            await message.answer("Нужен текст рассылки.", reply_markup=_cancel_kb())
            return
        if len(text) > 3500:
            await message.answer("Слишком длинно. Укороти текст (до 3500 символов).", reply_markup=_cancel_kb())
            return

        data = await state.get_data()
        date_s = str(data.get("broadcast_date") or "")
        user_ids = list(data.get("broadcast_user_ids") or [])
        await state.update_data(broadcast_text=text)

        await message.answer(
            f"📣 Broadcast на {date_s}\n"
            f"Получателей: {len(user_ids)}\n\n"
            "Текст:\n"
            f"{text}\n\n"
            "Отправить?",
            reply_markup=_broadcast_confirm_kb(),
        )

    @router.callback_query(F.data == "admin:bc:send")
    async def cb_admin_broadcast_send(call: CallbackQuery, state: FSMContext) -> None:
        if not call.message:
            await call.answer()
            return
        if not _is_admin_callback(call, settings):
            await call.answer("Нет доступа.", show_alert=True)
            return

        data = await state.get_data()
        text = str(data.get("broadcast_text") or "").strip()
        user_ids = list(data.get("broadcast_user_ids") or [])
        date_s = str(data.get("broadcast_date") or "")
        await state.clear()

        if not text or not user_ids:
            await call.message.answer("Нечего отправлять.", reply_markup=None)
            await _render_admin_status(call.message)
            await call.answer()
            return

        ok = 0
        fail = 0
        for uid in user_ids:
            try:
                await call.bot.send_message(int(uid), text)
                ok += 1
            except Exception:
                fail += 1
                logger.exception("Broadcast send failed", extra={"user_id": uid, "date": date_s})

        logger.info(
            "Broadcast finished",
            extra={"admin_id": settings.admin_id, "date": date_s, "ok": ok, "fail": fail, "total": len(user_ids)},
        )

        await call.message.answer(f"Готово. Отправлено: {ok}, ошибок: {fail}.", reply_markup=None)
        await _render_admin_status(call.message)
        await call.answer()

    return router

