from __future__ import annotations

import logging
import re
import asyncio
from datetime import date, datetime, time, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app_context import get_settings
from database import get_db
from handlers.states import BookingFSM
from handlers.moderation import moderation_kb
from services.meeting_formatter import format_admin_new_request
from services.google_api import get_freebusy
from logging_context import bind_meeting_id


logger = logging.getLogger(__name__)
router = Router(name="booking")


ALLOWED_DURATIONS = (15, 30, 60, 90)
WEEK_DAYS_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

UI_BOT_MESSAGE_IDS_KEY = "ui_bot_message_ids"
SUGGESTED_EMAIL_KEY = "suggested_email"
PREFILL_SUBJECT_KEY = "prefill_subject"
PREFILL_DESCRIPTION_KEY = "prefill_description"
PREFILL_EMAIL_KEY = "prefill_email"


async def _ui_register_bot(state: FSMContext, msg: Message) -> None:
    data = await state.get_data()
    ids = list(data.get(UI_BOT_MESSAGE_IDS_KEY) or [])
    ids.append(int(msg.message_id))
    await state.update_data(**{UI_BOT_MESSAGE_IDS_KEY: ids})


async def _try_delete_message(bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        # best-effort: Telegram может запретить удаление (или сообщение уже удалено/старое)
        logger.debug("Failed to delete message", extra={"chat_id": chat_id, "message_id": message_id})


async def _try_delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        logger.debug(
            "Failed to delete user message",
            extra={"chat_id": message.chat.id, "message_id": message.message_id},
        )


async def _ui_cleanup(bot, chat_id: int, state: FSMContext, *, keep_message_ids: set[int] | None = None) -> None:
    data = await state.get_data()
    ids = list(data.get(UI_BOT_MESSAGE_IDS_KEY) or [])
    if not ids:
        return
    keep = keep_message_ids or set()
    # удаляем в обратном порядке — так меньше шанс словить race на edit/delete
    kept: list[int] = []
    for mid in reversed(ids):
        try:
            mid_i = int(mid)
            if mid_i in keep:
                kept.append(mid_i)
                continue
            await _try_delete_message(bot, chat_id, mid_i)
        except Exception:
            continue
    # оставляем keep-идентификаторы, чтобы можно было удалить их позже
    await state.update_data(**{UI_BOT_MESSAGE_IDS_KEY: list(reversed(kept))})


def _name_suggest_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data="name:use"))
    kb.row(InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="name:manual"))
    return kb.as_markup()

def _email_suggest_kb(email: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    label = email if len(email) <= 60 else (email[:57] + "…")
    kb.row(InlineKeyboardButton(text=f"✅ Использовать {label}", callback_data="email:use"))
    kb.row(InlineKeyboardButton(text="✍️ Ввести другой", callback_data="email:manual"))
    kb.row(InlineKeyboardButton(text="Отмена", callback_data="email:cancel"))
    return kb.as_markup()


def _duration_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for minutes in ALLOWED_DURATIONS:
        kb.button(text=f"{minutes} мин", callback_data=f"dur:{minutes}")
    kb.adjust(2, 2)
    kb.row(InlineKeyboardButton(text="Отмена", callback_data="dur:cancel"))
    return kb.as_markup()

def _main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Записаться"), KeyboardButton(text="Мои заявки")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

def _desc_skip_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Пропустить", callback_data="desc:skip")
    kb.button(text="Отмена", callback_data="desc:cancel")
    kb.adjust(1, 1)
    return kb.as_markup()

async def _ask_email(message: Message, state: FSMContext, *, user: User) -> None:
    """
    Шаг email: если есть прошлый email — предложим использовать.
    """
    data = await state.get_data()
    prefill = str(data.get(PREFILL_EMAIL_KEY) or "").strip()
    if prefill:
        await state.update_data(**{SUGGESTED_EMAIL_KEY: prefill})
        msg = await message.answer(
            f"Нашёл email из прошлой заявки: <b>{prefill}</b>\nИспользовать?",
            reply_markup=_email_suggest_kb(prefill),
        )
        await _ui_register_bot(state, msg)
        return

    db = get_db()
    last = db.get_last_meeting_by_user(user.id)
    last_email = (last.user_email or "").strip() if last else ""

    if last_email:
        await state.update_data(**{SUGGESTED_EMAIL_KEY: last_email})
        msg = await message.answer(
            f"Нашёл прошлый email: <b>{last_email}</b>\nИспользовать?",
            reply_markup=_email_suggest_kb(last_email),
        )
        await _ui_register_bot(state, msg)
        return

    msg = await message.answer("Email?")
    await _ui_register_bot(state, msg)


async def start_booking_with_duration(message: Message, state: FSMContext, *, user: User, minutes: int) -> None:
    """
    Старт/продолжение booking, если длительность уже выбрана (в т.ч. из шаблона).
    """
    if get_db().is_user_blacklisted(user.id):
        await message.answer("Извини, запись недоступна.")
        return

    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.set_state(BookingFSM.date)
    await state.update_data(duration_minutes=int(minutes), week_offset=0)
    logger.info("Duration selected", extra={"user_id": user.id, "duration": int(minutes)})
    await _show_week(message, state)


async def _create_pending_and_notify(message: Message, state: FSMContext, *, user: User, email: str) -> None:
    """
    Финализация: создаём pending, уведомляем админа, отвечаем пользователю.
    Работает как из текстового ввода, так и из callback (email:use).
    """
    if not _is_valid_email(email):
        await message.answer("Похоже на некорректный email. Попробуй ещё раз.")
        return

    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.update_data(user_email=email)
    data = await state.get_data()

    db = get_db()
    tz_name = db.get_timezone()
    duration = int(data.get("duration_minutes", 30))
    time_local = str(data.get("time_local"))
    start_dt = datetime.strptime(time_local, "%Y-%m-%dT%H:%M")  # naive; create_meeting локализует через tz_name

    # анти-гонка: если Google Calendar доступен — проверим слот ещё раз прямо перед созданием pending
    try:
        import pytz

        tz = pytz.timezone(tz_name)
        start_local = tz.localize(start_dt)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = start_utc + timedelta(minutes=int(duration))
        busy_utc = await _fetch_busy_utc(start_utc, end_utc)
        if busy_utc and any(_overlaps(start_utc, end_utc, b0, b1) for (b0, b1) in busy_utc):
            logger.info(
                "Slot race detected before pending creation",
                extra={
                    "user_id": user.id,
                    "start_utc": start_utc.isoformat(),
                    "duration": duration,
                    "busy_count": len(busy_utc),
                },
            )
            await message.answer("Этот слот только что заняли. Выбери другое время.")
            await state.set_state(BookingFSM.time)
            await _show_times(message, state)
            return
    except Exception:
        logger.exception("Freebusy anti-race check failed; continuing", extra={"user_id": user.id})

    meeting_id = db.create_meeting(
        user_id=user.id,
        username=user.username,
        user_name=str(data.get("user_name") or ""),
        user_email=email,
        subject=str(data.get("subject") or ""),
        description=data.get("description"),
        start_time=start_dt,
        duration_minutes=duration,
        status="pending",
        timezone_name=tz_name,
    )

    logger.info("Meeting request created", extra={"user_id": user.id, "meeting_id": meeting_id})

    settings = get_settings()
    try:
        with bind_meeting_id(meeting_id):
            meeting = db.get_meeting(meeting_id)
            if meeting is None:
                raise RuntimeError("Meeting not found right after creation")
            text = format_admin_new_request(meeting, tz_name=tz_name)

        await message.bot.send_message(
            settings.admin_id,
            text,
            reply_markup=moderation_kb(meeting_id),
        )
    except Exception:
        logger.exception("Failed to notify admin", extra={"meeting_id": meeting_id})

    await state.clear()
    await message.answer(
        "Заявка отправлена Алексею на подтверждение.\n"
        "Как только он одобрит или отклонит её, я напишу тебе сюда — в этот чат с ботом.",
        reply_markup=_main_menu_kb(),
    )


def _parse_hhmm(value: str) -> time:
    s = value.strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM: {value!r}")
    h = int(parts[0])
    m = int(parts[1])
    return time(hour=h, minute=m)


def _round_up_to_30min(dt: datetime) -> datetime:
    minute = (dt.minute // 30) * 30
    base = dt.replace(minute=minute, second=0, microsecond=0)
    if base < dt:
        base += timedelta(minutes=30)
    return base


def _iter_slots(day: date, *, duration_minutes: int) -> list[datetime]:
    """
    Пока без Google freebusy: генерим слоты только по рабочим часам и буферу.

    Возвращает список datetime (локальная таймзона из настроек).
    """
    db = get_db()
    if db.is_date_blacklisted(day.isoformat()):
        return []

    tz_name = db.get_timezone()
    import pytz

    tz = pytz.timezone(tz_name)
    work = db.get_work_hours_for_date(day)
    if not work:
        return []
    work_start_s, work_end_s = work
    buffer_hours = db.get_buffer_hours()

    ws = _parse_hhmm(work_start_s)
    we = _parse_hhmm(work_end_s)
    start_dt = tz.localize(datetime.combine(day, ws))
    end_dt = tz.localize(datetime.combine(day, we))

    now = datetime.now(tz)
    if end_dt <= now:
        return []

    min_start = start_dt
    buffer_cutoff = now + timedelta(hours=buffer_hours)
    if buffer_cutoff > min_start:
        min_start = buffer_cutoff

    min_start = _round_up_to_30min(min_start)
    last_start = end_dt - timedelta(minutes=duration_minutes)
    if min_start > last_start:
        return []

    slots: list[datetime] = []
    cur = min_start
    while cur <= last_start:
        slots.append(cur)
        cur += timedelta(minutes=30)
    return slots


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _filter_busy(
    slots_local: list[datetime],
    *,
    duration_minutes: int,
    busy_utc: list[tuple[datetime, datetime]] | None,
) -> list[datetime]:
    if not busy_utc:
        return slots_local

    # слоты приходят локальные (aware); проверяем пересечение в UTC
    filtered: list[datetime] = []
    for s_local in slots_local:
        s_utc = s_local.astimezone(timezone.utc)
        e_utc = s_utc + timedelta(minutes=int(duration_minutes))
        if any(_overlaps(s_utc, e_utc, b0, b1) for (b0, b1) in busy_utc):
            continue
        filtered.append(s_local)
    return filtered


def _has_any_slot(day: date, *, duration_minutes: int, busy_utc: list[tuple[datetime, datetime]] | None = None) -> bool:
    """
    Пока без Google freebusy: считаем доступность только по рабочим часам, буферу и blacklist_dates.
    """
    slots = _iter_slots(day, duration_minutes=duration_minutes)
    slots = _filter_busy(slots, duration_minutes=duration_minutes, busy_utc=busy_utc)
    return bool(slots)


def _week_keyboard(
    *,
    week_start: date,
    week_offset: int,
    duration_minutes: int,
    busy_utc: list[tuple[datetime, datetime]] | None,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i in range(7):
        d = week_start + timedelta(days=i)
        ok = _has_any_slot(d, duration_minutes=duration_minutes, busy_utc=busy_utc)
        mark = "✅" if ok else "—"
        label = f"{WEEK_DAYS_RU[i]} {d.day:02d}.{d.month:02d} {mark}"
        if ok:
            kb.button(text=label, callback_data=f"date:{d.isoformat()}")
        else:
            kb.button(text=label, callback_data="date:na")
    kb.adjust(1, 1, 1, 1, 1, 1, 1)

    nav = InlineKeyboardBuilder()
    nav.button(text="⬅️ Назад", callback_data="date:back")
    nav.button(text="Следующая неделя ➡️", callback_data=f"week:{week_offset+1}")
    nav.adjust(2)

    kb.attach(nav)
    kb.row(InlineKeyboardButton(text="Отмена", callback_data="date:cancel"))
    return kb.as_markup()


async def _fetch_busy_utc(time_min_utc: datetime, time_max_utc: datetime) -> list[tuple[datetime, datetime]] | None:
    """
    Достаёт busy из Google Calendar. Если не настроено/ошибка — возвращает None (фолбэк без календаря).
    """
    settings = get_settings()
    if not settings.calendar_id:
        return None

    try:
        return await asyncio.to_thread(
            get_freebusy,
            calendar_id=settings.calendar_id,
            time_min_utc=time_min_utc,
            time_max_utc=time_max_utc,
            auth_mode=settings.google_auth_mode,
            service_account_json=settings.credentials_path,
            oauth_client_secrets_json=settings.oauth_client_secrets_path,
            oauth_token_json=settings.oauth_token_path,
        )
    except Exception:
        logger.exception("Google freebusy failed; fallback to local slots only")
        return None


async def _show_week(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    duration = int(data.get("duration_minutes", 30))
    week_offset = int(data.get("week_offset", 0))

    db = get_db()
    tz_name = db.get_timezone()
    import pytz

    tz = pytz.timezone(tz_name)
    today = datetime.now(tz).date()

    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=7)

    # запрашиваем busy на неделю одним запросом
    time_min_utc = tz.localize(datetime.combine(week_start, time.min)).astimezone(timezone.utc)
    time_max_utc = tz.localize(datetime.combine(week_end, time.min)).astimezone(timezone.utc)
    busy_utc = await _fetch_busy_utc(time_min_utc, time_max_utc)

    await _ui_cleanup(message.bot, message.chat.id, state)
    msg = await message.answer(
        "Выбери дату (показываю неделю):",
        reply_markup=_week_keyboard(
            week_start=week_start,
            week_offset=week_offset,
            duration_minutes=duration,
            busy_utc=busy_utc,
        ),
    )
    await _ui_register_bot(state, msg)

def _time_keyboard(*, slots: list[datetime]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for dt in slots:
        label = dt.strftime("%H:%M")
        payload = dt.strftime("%Y-%m-%dT%H:%M")
        kb.button(text=label, callback_data=f"time:{payload}")
    # 3 колонки обычно ок по ширине
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="time:back"))
    kb.row(InlineKeyboardButton(text="Отмена", callback_data="time:cancel"))
    return kb.as_markup()


async def _show_times(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    duration = int(data.get("duration_minutes", 30))
    raw_date = data.get("date")
    if not raw_date:
        await message.answer("Сначала выбери дату.")
        return
    d = date.fromisoformat(str(raw_date))

    # busy только на выбранный день
    db = get_db()
    tz_name = db.get_timezone()
    import pytz

    tz = pytz.timezone(tz_name)
    time_min_utc = tz.localize(datetime.combine(d, time.min)).astimezone(timezone.utc)
    time_max_utc = tz.localize(datetime.combine(d + timedelta(days=1), time.min)).astimezone(timezone.utc)
    busy_utc = await _fetch_busy_utc(time_min_utc, time_max_utc)

    slots = _iter_slots(d, duration_minutes=duration)
    slots = _filter_busy(slots, duration_minutes=duration, busy_utc=busy_utc)
    if not slots:
        await message.answer("На эту дату слотов нет. Выбери другую дату.")
        await _show_week(message, state)
        return

    await _ui_cleanup(message.bot, message.chat.id, state)
    msg = await message.answer("Выбери время:", reply_markup=_time_keyboard(slots=slots))
    await _ui_register_bot(state, msg)


async def _ensure_not_banned(message: Message) -> bool:
    if not message.from_user:
        return False
    if get_db().is_user_blacklisted(message.from_user.id):
        await message.answer("Извини, запись недоступна.")
        return False
    return True


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    logger.info("Booking cancelled by /cancel", extra={"user_id": message.from_user.id if message.from_user else None})
    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.clear()
    await message.answer("Ок, отменил.", reply_markup=_main_menu_kb())


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext) -> None:
    if not await _ensure_not_banned(message):
        return

    logger.info("Booking started", extra={"user_id": message.from_user.id if message.from_user else None})
    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.clear()
    await state.set_state(BookingFSM.duration)
    msg1 = await message.answer("Выбери длительность встречи:", reply_markup=ReplyKeyboardRemove())
    await _ui_register_bot(state, msg1)
    msg2 = await message.answer("Длительность:", reply_markup=_duration_kb())
    await _ui_register_bot(state, msg2)


@router.message(F.text.casefold() == "записаться")
async def text_book(message: Message, state: FSMContext) -> None:
    # удобный entrypoint, если пользователь нажмёт кнопку/введёт слово
    await cmd_book(message, state)


@router.callback_query(BookingFSM.duration, F.data.startswith("dur:"))
async def cb_duration(call: CallbackQuery, state: FSMContext) -> None:
    data = (call.data or "").split(":", 1)[1] if call.data else ""
    if data == "cancel":
        logger.info("Booking cancelled", extra={"user_id": call.from_user.id})
        if call.message:
            await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
        await state.clear()
        await call.message.edit_text("Ок, отменил.", reply_markup=None)  # type: ignore[union-attr]
        if call.message:
            await call.message.answer("Что дальше?", reply_markup=_main_menu_kb())
        await call.answer()
        return

    try:
        minutes = int(data)
    except ValueError:
        await call.answer("Некорректно.", show_alert=True)
        return

    if minutes not in ALLOWED_DURATIONS:
        await call.answer("Такой длительности нет.", show_alert=True)
        return
    if call.message:
        await call.message.edit_text(f"Ок, длительность {minutes} мин.", reply_markup=None)
        await start_booking_with_duration(call.message, state, user=call.from_user, minutes=minutes)
    await call.answer()


@router.callback_query(BookingFSM.date, F.data == "date:cancel")
async def cb_date_cancel(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Booking cancelled at date step", extra={"user_id": call.from_user.id})
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
    await state.clear()
    if call.message:
        await call.message.edit_text("Ок, отменил.", reply_markup=None)  # type: ignore[union-attr]
        await call.message.answer("Что дальше?", reply_markup=_main_menu_kb())
    await call.answer()


@router.callback_query(BookingFSM.date, F.data == "date:back")
async def cb_date_back(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Back to duration", extra={"user_id": call.from_user.id})
    await state.set_state(BookingFSM.duration)
    if call.message:
        await call.message.edit_text("Выбери длительность встречи:", reply_markup=_duration_kb())  # type: ignore[union-attr]
    await call.answer()


@router.callback_query(BookingFSM.date, F.data == "date:na")
async def cb_date_na(call: CallbackQuery) -> None:
    await call.answer("На эту дату слотов нет.", show_alert=True)


@router.callback_query(BookingFSM.date, F.data.startswith("week:"))
async def cb_week_nav(call: CallbackQuery, state: FSMContext) -> None:
    try:
        week_offset = int((call.data or "").split(":", 1)[1])
    except Exception:
        await call.answer("Некорректно.", show_alert=True)
        return

    await state.update_data(week_offset=week_offset)
    logger.info("Week changed", extra={"user_id": call.from_user.id, "week_offset": week_offset})
    if call.message:
        # вместо edit_text + answer (чтобы не плодить сообщения) — редактируем markup
        data = await state.get_data()
        duration = int(data.get("duration_minutes", 30))
        db = get_db()
        tz_name = db.get_timezone()
        import pytz

        tz = pytz.timezone(tz_name)
        today = datetime.now(tz).date()
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=7)

        time_min_utc = tz.localize(datetime.combine(week_start, time.min)).astimezone(timezone.utc)
        time_max_utc = tz.localize(datetime.combine(week_end, time.min)).astimezone(timezone.utc)
        busy_utc = await _fetch_busy_utc(time_min_utc, time_max_utc)

        await call.message.edit_reply_markup(  # type: ignore[union-attr]
            reply_markup=_week_keyboard(
                week_start=week_start,
                week_offset=week_offset,
                duration_minutes=duration,
                busy_utc=busy_utc,
            )
        )
    await call.answer()


@router.callback_query(BookingFSM.date, F.data.startswith("date:"))
async def cb_date_select(call: CallbackQuery, state: FSMContext) -> None:
    # date:YYYY-MM-DD
    raw = (call.data or "").split(":", 1)[1]
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        await call.answer("Некорректная дата.", show_alert=True)
        return

    data = await state.get_data()
    duration = int(data.get("duration_minutes", 30))
    if not _has_any_slot(d, duration_minutes=duration):
        await call.answer("На эту дату слотов нет.", show_alert=True)
        return

    await state.update_data(date=d.isoformat())
    logger.info("Date selected", extra={"user_id": call.from_user.id, "date": d.isoformat()})
    await state.set_state(BookingFSM.time)

    if call.message:
        await call.message.edit_text(
            f"Ок, дата {d.day:02d}.{d.month:02d}.{d.year}.\n"
            "Выбирай время."
        )  # type: ignore[union-attr]
        await _show_times(call.message, state)
    await call.answer()


@router.callback_query(BookingFSM.time, F.data == "time:cancel")
async def cb_time_cancel(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Booking cancelled at time step", extra={"user_id": call.from_user.id})
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
    await state.clear()
    if call.message:
        await call.message.edit_text("Ок, отменил.", reply_markup=None)  # type: ignore[union-attr]
        await call.message.answer("Что дальше?", reply_markup=_main_menu_kb())
    await call.answer()


@router.callback_query(BookingFSM.time, F.data == "time:back")
async def cb_time_back(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Back to week from time", extra={"user_id": call.from_user.id})
    await state.set_state(BookingFSM.date)
    if call.message:
        await call.message.edit_text("Ок, вернул к выбору даты.", reply_markup=None)  # type: ignore[union-attr]
        await _show_week(call.message, state)
    await call.answer()


@router.callback_query(BookingFSM.time, F.data.startswith("time:"))
async def cb_time_select(call: CallbackQuery, state: FSMContext) -> None:
    raw = (call.data or "").split(":", 1)[1]
    try:
        # локальная дата/время в формате YYYY-MM-DDTHH:MM
        chosen = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        await call.answer("Некорректное время.", show_alert=True)
        return

    # Валидация: слот всё ещё доступен по нашим правилам (без Google)
    data = await state.get_data()
    duration = int(data.get("duration_minutes", 30))
    d = date.fromisoformat(str(data.get("date")))
    slots = {dt.strftime("%Y-%m-%dT%H:%M") for dt in _iter_slots(d, duration_minutes=duration)}
    if raw not in slots:
        await call.answer("Этот слот уже недоступен.", show_alert=True)
        return

    await state.update_data(time_local=raw)
    logger.info("Time selected", extra={"user_id": call.from_user.id, "time_local": raw})

    if call.message:
        await call.message.edit_text(
            f"Ок, время {chosen.strftime('%H:%M')}.",
            reply_markup=None,
        )  # type: ignore[union-attr]

        await _ui_cleanup(call.bot, call.message.chat.id, state)
        suggested = (call.from_user.full_name or "").strip() if call.from_user else ""
        if suggested and len(suggested) <= 120:
            await state.update_data(suggested_name=suggested)
            logger.info("Suggesting Telegram full_name", extra={"user_id": call.from_user.id})
            msg = await call.message.answer(
                f"Нашёл имя в Telegram: <b>{suggested}</b>\nПодтвердить?",
                reply_markup=_name_suggest_kb(),
            )
            await _ui_register_bot(state, msg)
        else:
            msg1 = await call.message.answer("Как тебя зовут?")
            await _ui_register_bot(state, msg1)
            msg2 = await call.message.answer("Имя:", reply_markup=ReplyKeyboardRemove())
            await _ui_register_bot(state, msg2)
    await call.answer()

    await state.set_state(BookingFSM.name)


@router.callback_query(BookingFSM.name, F.data == "name:use")
async def cb_name_use(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    suggested = str(data.get("suggested_name") or "").strip()
    if not suggested:
        await call.answer("Не нашёл имя. Введи вручную.", show_alert=True)
        return

    await state.update_data(user_name=suggested)
    logger.info("Name confirmed from Telegram", extra={"user_id": call.from_user.id})
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state)

        data = await state.get_data()
        prefill_subject = str(data.get(PREFILL_SUBJECT_KEY) or "").strip()
        if prefill_subject:
            await state.update_data(subject=prefill_subject)
            logger.info("Subject prefilled", extra={"user_id": call.from_user.id})
            prefill_description = data.get(PREFILL_DESCRIPTION_KEY)
            if prefill_description is not None:
                await state.update_data(description=prefill_description)
                logger.info("Description prefilled", extra={"user_id": call.from_user.id})
                await state.set_state(BookingFSM.email)
                await _ask_email(call.message, state, user=call.from_user)
            else:
                await state.set_state(BookingFSM.description)
                msg = await call.message.answer(
                    "Описание (можно ссылку на Zoom/Meet). Если не нужно — нажми «Пропустить».",
                    reply_markup=_desc_skip_kb(),
                )
                await _ui_register_bot(state, msg)
        else:
            await state.set_state(BookingFSM.subject)
            msg = await call.message.answer("Тема встречи?")
            await _ui_register_bot(state, msg)
    await call.answer()


@router.callback_query(BookingFSM.name, F.data == "name:manual")
async def cb_name_manual(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Name manual entry selected", extra={"user_id": call.from_user.id})
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state)
        msg1 = await call.message.answer("Как тебя зовут?")
        await _ui_register_bot(state, msg1)
        msg2 = await call.message.answer("Имя:", reply_markup=ReplyKeyboardRemove())
        await _ui_register_bot(state, msg2)
    await call.answer()


@router.message(BookingFSM.name)
async def st_name(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введи имя текстом.")
        return
    if len(text) > 120:
        await message.answer("Слишком длинно. Введи короче (до 120 символов).")
        return

    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.update_data(user_name=text)
    await _try_delete_user_message(message)
    logger.info("Name collected", extra={"user_id": message.from_user.id if message.from_user else None})
    data = await state.get_data()
    prefill_subject = str(data.get(PREFILL_SUBJECT_KEY) or "").strip()
    if prefill_subject:
        await state.update_data(subject=prefill_subject)
        logger.info("Subject prefilled", extra={"user_id": message.from_user.id if message.from_user else None})
        prefill_description = data.get(PREFILL_DESCRIPTION_KEY)
        if prefill_description is not None:
            await state.update_data(description=prefill_description)
            logger.info("Description prefilled", extra={"user_id": message.from_user.id if message.from_user else None})
            await state.set_state(BookingFSM.email)
            if message.from_user:
                await _ask_email(message, state, user=message.from_user)
        else:
            await state.set_state(BookingFSM.description)
            msg = await message.answer(
                "Описание (можно ссылку на Zoom/Meet). Если не нужно — нажми «Пропустить».",
                reply_markup=_desc_skip_kb(),
            )
            await _ui_register_bot(state, msg)
        return

    await state.set_state(BookingFSM.subject)
    msg = await message.answer("Тема встречи?")
    await _ui_register_bot(state, msg)


@router.message(BookingFSM.subject)
async def st_subject(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введи тему текстом.")
        return
    if len(text) > 200:
        await message.answer("Слишком длинно. Введи короче (до 200 символов).")
        return

    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.update_data(subject=text)
    await _try_delete_user_message(message)
    logger.info("Subject collected", extra={"user_id": message.from_user.id if message.from_user else None})
    await state.set_state(BookingFSM.description)
    msg = await message.answer(
        "Описание (можно ссылку на Zoom/Meet). Если не нужно — нажми «Пропустить».",
        reply_markup=_desc_skip_kb(),
    )
    await _ui_register_bot(state, msg)


@router.callback_query(BookingFSM.description, F.data == "desc:skip")
async def cb_desc_skip(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Description skipped", extra={"user_id": call.from_user.id})
    await state.update_data(description=None)
    await state.set_state(BookingFSM.email)
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
        await call.message.edit_text("Ок, без описания.", reply_markup=None)  # type: ignore[union-attr]
        if call.from_user:
            await _ask_email(call.message, state, user=call.from_user)
    await call.answer()


@router.callback_query(BookingFSM.description, F.data == "desc:cancel")
async def cb_desc_cancel(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Booking cancelled at description step", extra={"user_id": call.from_user.id})
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
    await state.clear()
    if call.message:
        await call.message.edit_text("Ок, отменил.", reply_markup=None)  # type: ignore[union-attr]
        await call.message.answer("Что дальше?", reply_markup=_main_menu_kb())
    await call.answer()


@router.message(BookingFSM.description)
async def st_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введи описание текстом или нажми «Пропустить».")
        return
    if len(text) > 2000:
        await message.answer("Слишком длинно. Введи короче (до 2000 символов) или нажми «Пропустить».")
        return

    await _ui_cleanup(message.bot, message.chat.id, state)
    await state.update_data(description=text)
    await _try_delete_user_message(message)
    logger.info("Description collected", extra={"user_id": message.from_user.id if message.from_user else None})
    await state.set_state(BookingFSM.email)
    if message.from_user:
        await _ask_email(message, state, user=message.from_user)


def _is_valid_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_RE.match(email))


@router.message(BookingFSM.email)
async def st_email(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return
    email = (message.text or "").strip()
    await _try_delete_user_message(message)
    await _create_pending_and_notify(message, state, user=message.from_user, email=email)


@router.callback_query(BookingFSM.email, F.data == "email:manual")
async def cb_email_manual(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return
    if not call.from_user:
        await call.answer()
        return
    await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
    await call.message.edit_text("Ок, введи email текстом.", reply_markup=None)  # type: ignore[union-attr]
    msg = await call.message.answer("Email?")
    await _ui_register_bot(state, msg)
    await call.answer()


@router.callback_query(BookingFSM.email, F.data == "email:cancel")
async def cb_email_cancel(call: CallbackQuery, state: FSMContext) -> None:
    logger.info("Booking cancelled at email step", extra={"user_id": call.from_user.id if call.from_user else None})
    if call.message:
        await _ui_cleanup(call.bot, call.message.chat.id, state, keep_message_ids={call.message.message_id})
    await state.clear()
    if call.message:
        await call.message.edit_text("Ок, отменил.", reply_markup=None)  # type: ignore[union-attr]
        await call.message.answer("Что дальше?", reply_markup=_main_menu_kb())
    await call.answer()


@router.callback_query(BookingFSM.email, F.data == "email:use")
async def cb_email_use(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return
    if not call.from_user:
        await call.answer()
        return
    data = await state.get_data()
    email = str(data.get(SUGGESTED_EMAIL_KEY) or "").strip()
    if not email:
        await call.answer("Не нашёл прошлый email. Введи вручную.", show_alert=True)
        return

    await call.message.edit_text("Ок, использую прошлый email.", reply_markup=None)  # type: ignore[union-attr]
    await _create_pending_and_notify(call.message, state, user=call.from_user, email=email)
    await call.answer()
