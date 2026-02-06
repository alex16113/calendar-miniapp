from __future__ import annotations

import logging
from datetime import timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app_context import get_settings
from database import get_db
from services.meeting_formatter import format_local_datetime


logger = logging.getLogger(__name__)
router = Router(name="my_requests")

PAGE_SIZE = 5
STATUSES = ("pending", "confirmed")


def _status_label(status: str) -> str:
    return {
        "pending": "⏳ pending",
        "confirmed": "✅ confirmed",
        "rejected": "❌ rejected",
        "expired": "⌛️ expired",
        "cancelled": "🗑️ cancelled",
    }.get(status, status)


def _list_text(*, meetings: list, tz_name: str, page: int, total: int, total_pages: int) -> str:
    header = f"📌 Мои заявки: {total}\nСтраница: {page+1}/{max(1,total_pages)}\n"
    if not meetings:
        return header + "\nПусто."
    lines: list[str] = []
    for m in meetings:
        when = format_local_datetime(m.start_time, tz_name)
        subject = (m.subject or "").strip() or "(без темы)"
        lines.append(f"#{m.id} | {when} | {_status_label(m.status)} | {subject}")
    return header + "\n" + "\n".join(lines)


def _kb(*, meetings: list, page: int, total: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for m in meetings:
        mid = int(m.id or 0)
        if mid <= 0:
            continue
        if m.status == "pending":
            kb.row(
                InlineKeyboardButton(text=f"🗑️ Отменить #{mid}", callback_data=f"my:cancel:{mid}:{page}"),
            )
        elif m.status == "confirmed":
            row: list[InlineKeyboardButton] = []
            if m.google_event_html_link:
                row.append(InlineKeyboardButton(text=f"📅 #{mid}", url=str(m.google_event_html_link)))
            if row:
                kb.row(*row)

    kb.row(InlineKeyboardButton(text="➕ Новая заявка (как прошлый раз)", callback_data="my:new_from_last"))

    total_pages = max(1, (int(total) + PAGE_SIZE - 1) // PAGE_SIZE)
    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="⬅️", callback_data=f"my:page:{page-1}")
    if page + 1 < total_pages:
        nav.button(text="➡️", callback_data=f"my:page:{page+1}")
    nav.button(text="🔄", callback_data=f"my:page:{page}")
    nav.adjust(3)
    kb.attach(nav)

    kb.row(InlineKeyboardButton(text="Закрыть", callback_data="my:close"))
    return kb.as_markup()


async def _render(message: Message, *, user_id: int, page: int) -> None:
    db = get_db()
    total = db.count_user_meetings(user_id=user_id, statuses=STATUSES)
    total_pages = max(1, (int(total) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_i = max(0, min(int(page), total_pages - 1))
    meetings = db.list_user_meetings(user_id=user_id, statuses=STATUSES, limit=PAGE_SIZE, offset=page_i * PAGE_SIZE)
    tz_name = db.get_timezone()
    await message.answer(
        _list_text(meetings=meetings, tz_name=tz_name, page=page_i, total=total, total_pages=total_pages),
        reply_markup=_kb(meetings=meetings, page=page_i, total=total),
    )


async def _render_edit(call: CallbackQuery, *, user_id: int, page: int) -> None:
    if not call.message:
        await call.answer()
        return
    db = get_db()
    total = db.count_user_meetings(user_id=user_id, statuses=STATUSES)
    total_pages = max(1, (int(total) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_i = max(0, min(int(page), total_pages - 1))
    meetings = db.list_user_meetings(user_id=user_id, statuses=STATUSES, limit=PAGE_SIZE, offset=page_i * PAGE_SIZE)
    tz_name = db.get_timezone()
    await call.message.edit_text(
        _list_text(meetings=meetings, tz_name=tz_name, page=page_i, total=total, total_pages=total_pages),
        reply_markup=_kb(meetings=meetings, page=page_i, total=total),
    )
    await call.answer()


@router.message(Command("my"))
async def cmd_my(message: Message) -> None:
    if not message.from_user:
        return
    logger.info("My requests opened", extra={"user_id": message.from_user.id})
    await _render(message, user_id=message.from_user.id, page=0)


@router.message(F.text.casefold() == "мои заявки")
async def text_my(message: Message) -> None:
    await cmd_my(message)


@router.callback_query(F.data.startswith("my:page:"))
async def cb_my_page(call: CallbackQuery) -> None:
    if not call.from_user:
        await call.answer()
        return
    try:
        page = int((call.data or "").split("my:page:", 1)[1])
    except Exception:
        await call.answer("Некорректно.", show_alert=True)
        return
    await _render_edit(call, user_id=call.from_user.id, page=page)


@router.callback_query(F.data == "my:close")
async def cb_my_close(call: CallbackQuery) -> None:
    if call.message:
        await call.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
    await call.answer()


@router.callback_query(F.data.startswith("my:cancel:"))
async def cb_my_cancel_pending(call: CallbackQuery) -> None:
    if not call.from_user:
        await call.answer()
        return
    # my:cancel:<meeting_id>:<page>
    try:
        parts = (call.data or "").split(":")
        meeting_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    except Exception:
        await call.answer("Некорректно.", show_alert=True)
        return

    db = get_db()
    m = db.get_meeting(meeting_id)
    if m is None:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
    if m.user_id != call.from_user.id:
        await call.answer("Нет доступа.", show_alert=True)
        return
    if m.status != "pending":
        await call.answer(f"Уже не pending (status={m.status}).", show_alert=True)
        return

    ok = db.update_meeting_status_if_current(meeting_id, from_status="pending", to_status="cancelled")
    if not ok:
        await call.answer("Не смог отменить (возможно уже обработано).", show_alert=True)
        return

    logger.info("User cancelled pending meeting", extra={"user_id": call.from_user.id, "meeting_id": meeting_id})

    # уведомим админа (чтобы не подтверждал по старому сообщению)
    s = get_settings()
    try:
        tz = db.get_timezone()
        when = format_local_datetime(m.start_time, tz)
        await call.bot.send_message(
            s.admin_id,
            "🗑️ Пользователь отменил заявку.\n"
            f"ID: {m.id}\n"
            f"Пользователь: {call.from_user.id} (@{call.from_user.username})\n"
            f"Время: {when} ({m.duration} мин)\n"
            f"Тема: {(m.subject or '').strip() or '(без темы)'}",
        )
    except Exception:
        logger.exception("Failed to notify admin about user cancellation", extra={"meeting_id": meeting_id, "admin_id": s.admin_id})

    await _render_edit(call, user_id=call.from_user.id, page=page)


@router.callback_query(F.data == "my:new_from_last")
async def cb_my_new_from_last(call: CallbackQuery, state: FSMContext) -> None:
    if not call.message:
        await call.answer()
        return
    if not call.from_user:
        await call.answer()
        return

    db = get_db()
    last = db.get_last_meeting_by_user(call.from_user.id)
    if last is None:
        await call.answer("Нет прошлых заявок с email.", show_alert=True)
        return

    # предзаполним поля анкеты из последней заявки
    await state.clear()
    await state.update_data(
        prefill_subject=(last.subject or ""),
        prefill_description=last.description,  # может быть None
        prefill_email=(last.user_email or ""),
    )

    # стартуем booking сразу с прошлой длительностью
    try:
        from handlers.booking import start_booking_with_duration

        await start_booking_with_duration(call.message, state, user=call.from_user, minutes=int(last.duration))
    except Exception:
        logger.exception("Failed to start booking from template", extra={"user_id": call.from_user.id})
        await call.answer("Не смог стартовать booking. См. логи.", show_alert=True)
        return

    await call.answer()

