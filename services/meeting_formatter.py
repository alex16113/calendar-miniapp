from __future__ import annotations

from datetime import datetime, timezone

import pytz

from database.database import Meeting


def format_local_datetime(dt_utc: datetime, tz_name: str) -> str:
    tz = pytz.timezone(tz_name)
    return dt_utc.astimezone(timezone.utc).astimezone(tz).strftime("%d.%m.%Y %H:%M")


def format_admin_new_request(meeting: Meeting, *, tz_name: str) -> str:
    username = f"@{meeting.username}" if meeting.username else "(без username)"
    name = (meeting.user_name or "").strip() or "(без имени)"
    email = (meeting.user_email or "").strip() or "(без email)"
    subject = (meeting.subject or "").strip() or "(без темы)"
    description = (meeting.description or "").strip() or "отсутствует"
    when = format_local_datetime(meeting.start_time, tz_name)

    return (
        "🔔 Новая заявка!\n"
        f"👤 Имя: {name} ({username})\n"
        f"📧 Email: {email}\n"
        f"📝 Тема: {subject}\n"
        f"📄 Описание: {description}\n"
        f"⏰ Время: {when} ({meeting.duration} мин)\n"
        f"ID: {meeting.id}"
    )


def format_admin_pending_details(meeting: Meeting, *, tz_name: str) -> str:
    # по сути та же карточка, но с явной пометкой pending
    return "🔔 Pending заявка\n" + format_admin_new_request(meeting, tz_name=tz_name).replace("🔔 Новая заявка!\n", "", 1)


def format_user_confirmed(meeting: Meeting, *, tz_name: str) -> str:
    when = format_local_datetime(meeting.start_time, tz_name)
    return f"✅ Встреча подтверждена!\nВремя: {when} ({meeting.duration} мин)"


def format_user_banned(meeting: Meeting, *, tz_name: str) -> str:
    when = format_local_datetime(meeting.start_time, tz_name)
    return f"Запись недоступна.\nВремя: {when} ({meeting.duration} мин)"


def format_user_rejected(meeting: Meeting, *, tz_name: str, reason: str | None = None) -> str:
    when = format_local_datetime(meeting.start_time, tz_name)
    reason_line = f"Причина: {reason}\n" if reason else ""
    return f"❌ Заявка на встречу отклонена.\n{reason_line}Время: {when} ({meeting.duration} мин)"


def format_user_expired(meeting: Meeting, *, tz_name: str) -> str:
    when = format_local_datetime(meeting.start_time, tz_name)
    return (
        "⌛️ Заявка на встречу истекла (не была подтверждена вовремя).\n"
        f"Время: {when} ({meeting.duration} мин)\n"
        "Чтобы записаться заново — /book"
    )

