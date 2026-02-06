from __future__ import annotations

import asyncio
import logging
from datetime import timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app_context import get_settings
from database import get_db
from services.google_api import create_event, get_freebusy
from services.meeting_formatter import format_local_datetime, format_user_banned, format_user_confirmed, format_user_rejected
from handlers.states import ModerationFSM
from logging_context import bind_meeting_id
from services.meeting_formatter import format_admin_new_request


logger = logging.getLogger(__name__)
router = Router(name="moderation")

def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end

def _extract_meet_link(event: dict) -> str | None:
    # 1) старое поле
    link = (event or {}).get("hangoutLink")
    if link:
        return str(link)
    # 2) conferenceData.entryPoints[].uri
    conf = (event or {}).get("conferenceData") or {}
    eps = conf.get("entryPoints") or []
    for ep in eps:
        try:
            if not isinstance(ep, dict):
                continue
            uri = ep.get("uri")
            if uri:
                return str(uri)
        except Exception:
            continue
    return None


async def _maybe_send_next_pending(bot, *, admin_chat_id: int) -> None:
    """
    После обработки заявки автоматически подсовываем следующую pending,
    чтобы админ мог “потоком” модерировать.
    """
    db = get_db()
    items = db.list_pending_meetings(limit=1, offset=0)
    if not items:
        return
    m = items[0]
    if not m.id:
        return
    tz_name = db.get_timezone()
    with bind_meeting_id(m.id):
        try:
            await bot.send_message(
                admin_chat_id,
                "Следующая заявка:\n\n" + format_admin_new_request(m, tz_name=tz_name),
                reply_markup=moderation_kb(int(m.id)),
            )
        except Exception:
            logger.exception("Failed to send next pending to admin", extra={"meeting_id": m.id, "admin_chat_id": admin_chat_id})


def moderation_kb(meeting_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # В 1 ряд не влезает на мобиле — делаем по строке на действие.
    kb.row(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"meet:confirm:{meeting_id}"))
    kb.row(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"meet:reject:{meeting_id}"))
    kb.row(InlineKeyboardButton(text="🚫 В бан", callback_data=f"meet:ban:{meeting_id}"))
    return kb.as_markup()


def _is_admin(user_id: int) -> bool:
    return user_id == get_settings().admin_id


@router.callback_query(F.data.startswith("meet:"))
async def cb_meeting_action(call: CallbackQuery, state: FSMContext) -> None:
    if not call.from_user or not _is_admin(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return

    parts = (call.data or "").split(":")
    if len(parts) != 3:
        await call.answer("Некорректно.", show_alert=True)
        return

    _, action, raw_id = parts
    try:
        meeting_id = int(raw_id)
    except ValueError:
        await call.answer("Некорректно.", show_alert=True)
        return

    with bind_meeting_id(meeting_id):
        await _cb_meeting_action_inner(call, state, meeting_id=meeting_id, action=action)
    return


async def _cb_meeting_action_inner(call: CallbackQuery, state: FSMContext, *, meeting_id: int, action: str) -> None:
    # Если админ уже в процессе отклонения — блокируем остальные действия, чтобы не “поймать” случайный текст.
    cur_state = await state.get_state()
    if cur_state == ModerationFSM.reject_reason.state and action not in ("reject", "reject_cancel"):
        data = await state.get_data()
        if int(data.get("meeting_id") or 0) == meeting_id:
            await call.answer("Сначала отправь причину отклонения или нажми «Отмена».", show_alert=True)
            return

    db = get_db()
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        await call.answer("Заявка не найдена.", show_alert=True)
        return

    if meeting.status != "pending":
        if meeting.status == "expired":
            await call.answer("Заявка истекла.", show_alert=True)
        else:
            await call.answer(f"Уже обработано (status={meeting.status}).", show_alert=True)
        return

    # применяем действие
    user_markup: InlineKeyboardMarkup | None = None
    if action == "confirm":
        settings = get_settings()
        if not settings.calendar_id:
            await call.answer("CALENDAR_ID не задан. Нельзя подтвердить.", show_alert=True)
            return

        use_oauth = settings.google_auth_mode == "oauth"

        # анти-гонка: перед insert проверяем, что слот всё ещё свободен в календаре
        try:
            start_utc = meeting.start_time
            end_utc = start_utc + timedelta(minutes=int(meeting.duration))
            busy = await asyncio.to_thread(
                get_freebusy,
                calendar_id=settings.calendar_id,
                time_min_utc=start_utc,
                time_max_utc=end_utc,
                auth_mode=settings.google_auth_mode,
                service_account_json=settings.credentials_path,
                oauth_client_secrets_json=settings.oauth_client_secrets_path,
                oauth_token_json=settings.oauth_token_path,
            )
        except Exception:
            logger.exception("Freebusy check failed before confirm", extra={"meeting_id": meeting_id})
            await call.answer("Не смог проверить занятость в календаре. Попробуй ещё раз.", show_alert=True)
            return

        if busy and any(_overlaps(start_utc, end_utc, b0, b1) for (b0, b1) in busy):
            logger.info("Confirm blocked: slot is busy in calendar", extra={"meeting_id": meeting_id, "busy_count": len(busy)})
            await call.answer("Слот уже занят в календаре. Нельзя подтвердить.", show_alert=True)
            return

        # сначала создаём event в Google (чтобы не подтверждать без календаря)
        try:
            desc = meeting.description or ""
            if meeting.user_email:
                desc = (desc + "\n\n" if desc else "") + f"Email клиента: {meeting.user_email}"
            created = await asyncio.to_thread(
                create_event,
                calendar_id=settings.calendar_id,
                start_utc=meeting.start_time,
                duration_minutes=meeting.duration,
                summary=meeting.subject or "Встреча",
                description=desc,
                attendee_email=meeting.user_email if use_oauth else None,
                create_meet=True if use_oauth else False,
                auth_mode=settings.google_auth_mode,
                service_account_json=settings.credentials_path,
                oauth_client_secrets_json=settings.oauth_client_secrets_path,
                oauth_token_json=settings.oauth_token_path,
                send_updates="all" if use_oauth else "none",
            )
        except Exception:
            logger.exception("Google create_event failed", extra={"meeting_id": meeting_id})
            await call.answer("Не смог создать событие в Google Calendar.", show_alert=True)
            return

        created = created or {}
        event_id = created.get("id")
        html_link = created.get("htmlLink")
        meet_link = _extract_meet_link(created)
        try:
            db.set_meeting_google_event(
                meeting_id,
                event_id=str(event_id) if event_id else None,
                html_link=str(html_link) if html_link else None,
                meet_link=str(meet_link) if meet_link else None,
            )
        except Exception:
            logger.exception("Failed to persist google event data", extra={"meeting_id": meeting_id})

        db.update_meeting_status(meeting_id, "confirmed")
        # Ссылка на событие в календаре (htmlLink). Для OAuth-схемы инвайт придёт на email,
        # а Meet будет внутри события.
        meeting = db.get_meeting(meeting_id) or meeting
        user_text = format_user_confirmed(meeting, tz_name=db.get_timezone())
        buttons: list[list[InlineKeyboardButton]] = []
        if html_link:
            buttons.append([InlineKeyboardButton(text="📅 Открыть событие в календаре", url=str(html_link))])
        if buttons:
            user_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        admin_mark = "✅ Подтверждено"
    elif action == "reject":
        # Запрашиваем причину текстом.
        await state.set_state(ModerationFSM.reject_reason)
        await state.update_data(meeting_id=meeting_id)
        await call.message.answer(  # type: ignore[union-attr]
            f"❌ Отклонение заявки ID {meeting_id}.\n"
            "Напиши причину отклонения одним сообщением.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Отмена", callback_data=f"meet:reject_cancel:{meeting_id}")]
                ]
            ),
        )
        await call.answer("Жду причину.")
        return
    elif action == "reject_cancel":
        cur_state = await state.get_state()
        if cur_state == ModerationFSM.reject_reason.state:
            data = await state.get_data()
            if int(data.get("meeting_id") or 0) == meeting_id:
                await state.clear()
                await call.answer("Ок, отменил отклонение.")
                return
        await call.answer("Нечего отменять.", show_alert=True)
        return
    elif action == "ban":
        db.blacklist_user(meeting.user_id)
        db.update_meeting_status(meeting_id, "rejected")
        meeting = db.get_meeting(meeting_id) or meeting
        user_text = format_user_banned(meeting, tz_name=db.get_timezone())
        admin_mark = "🚫 Пользователь забанен"
    else:
        await call.answer("Неизвестное действие.", show_alert=True)
        return

    tz_name = db.get_timezone()
    when = format_local_datetime(meeting.start_time, tz_name)

    logger.info(
        "Meeting moderated",
        extra={"meeting_id": meeting_id, "action": action, "admin_id": call.from_user.id},
    )

    # уведомляем пользователя
    try:
        await call.bot.send_message(
            meeting.user_id,
            user_text if action in ("confirm", "ban") else f"{user_text}\nВремя: {when} ({meeting.duration} мин)",
            reply_markup=user_markup,
        )
    except Exception:
        logger.exception("Failed to notify user", extra={"meeting_id": meeting_id, "user_id": meeting.user_id})

    # обновляем сообщение админа и убираем кнопки
    if call.message:
        try:
            await call.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
            await call.message.answer(f"{admin_mark} (ID: {meeting_id})")
        except Exception:
            logger.exception("Failed to update admin message", extra={"meeting_id": meeting_id})

    # Автопереход к следующей заявке (для confirm/ban; reject завершится в st_reject_reason).
    if action in ("confirm", "ban") and call.from_user:
        await _maybe_send_next_pending(call.bot, admin_chat_id=call.from_user.id)

    await call.answer("Готово.")


@router.message(ModerationFSM.reject_reason)
async def st_reject_reason(message: Message, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await state.clear()
        return

    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Нужна причина отклонения текстом. Напиши одним сообщением.")
        return
    if len(reason) > 1000:
        await message.answer("Слишком длинно. Напиши короче (до 1000 символов).")
        return

    data = await state.get_data()
    try:
        meeting_id = int(data.get("meeting_id") or 0)
    except Exception:
        meeting_id = 0
    if meeting_id <= 0:
        await state.clear()
        await message.answer("Не понял, какую заявку отклонять. Нажми ❌ ещё раз.")
        return

    db = get_db()
    meeting = db.get_meeting(meeting_id)
    if meeting is None:
        await state.clear()
        await message.answer("Заявка не найдена.")
        return
    if meeting.status != "pending":
        await state.clear()
        await message.answer(f"Уже обработано (status={meeting.status}).")
        return

    db.update_meeting_status(meeting_id, "rejected")

    tz_name = db.get_timezone()

    logger.info(
        "Meeting rejected with reason",
        extra={"meeting_id": meeting_id, "admin_id": message.from_user.id},
    )

    # уведомляем пользователя
    try:
        await message.bot.send_message(
            meeting.user_id,
            format_user_rejected(meeting, tz_name=tz_name, reason=reason),
        )
    except Exception:
        logger.exception("Failed to notify user about rejection", extra={"meeting_id": meeting_id, "user_id": meeting.user_id})

    await state.clear()
    await message.answer(f"❌ Отклонено (ID: {meeting_id}). Причина отправлена пользователю.")

    # Автопереход к следующей заявке после reject.
    try:
        await _maybe_send_next_pending(message.bot, admin_chat_id=message.chat.id)
    except Exception:
        logger.exception("Failed to send next pending after reject", extra={"meeting_id": meeting_id})

