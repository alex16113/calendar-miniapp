"""
Логика слотов для API: неделя (флаги по дням), слоты на день.
Переиспользует правила из БД и Google freebusy, как в handlers/booking.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone

import pytz

from database import get_db
from app_context import get_settings
from services.google_api import get_freebusy

logger = logging.getLogger(__name__)


def _parse_hhmm(value: str) -> time:
    s = value.strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM: {value!r}")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def _round_up_to_30min(dt: datetime) -> datetime:
    minute = (dt.minute // 30) * 30
    base = dt.replace(minute=minute, second=0, microsecond=0)
    if base < dt:
        base += timedelta(minutes=30)
    return base


def _overlaps(
    a_start: datetime, a_end: datetime,
    b_start: datetime, b_end: datetime,
) -> bool:
    return a_start < b_end and b_start < a_end


def _iter_slots(day: date, *, duration_minutes: int) -> list[datetime]:
    """Слоты на день по рабочим часам, буферу и blacklist (без freebusy)."""
    db = get_db()
    if db.is_date_blacklisted(day.isoformat()):
        return []
    tz_name = db.get_timezone()
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


def _filter_busy(
    slots_local: list[datetime],
    *,
    duration_minutes: int,
    busy_utc: list[tuple[datetime, datetime]] | None,
) -> list[datetime]:
    if not busy_utc:
        return slots_local
    filtered: list[datetime] = []
    for s_local in slots_local:
        s_utc = s_local.astimezone(timezone.utc)
        e_utc = s_utc + timedelta(minutes=duration_minutes)
        if any(_overlaps(s_utc, e_utc, b0, b1) for (b0, b1) in busy_utc):
            continue
        filtered.append(s_local)
    return filtered


async def _fetch_busy_utc(
    time_min_utc: datetime,
    time_max_utc: datetime,
) -> list[tuple[datetime, datetime]] | None:
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


def _has_any_slot(
    day: date,
    *,
    duration_minutes: int,
    busy_utc: list[tuple[datetime, datetime]] | None = None,
) -> bool:
    slots = _iter_slots(day, duration_minutes=duration_minutes)
    slots = _filter_busy(slots, duration_minutes=duration_minutes, busy_utc=busy_utc)
    return bool(slots)


async def get_week_slots(
    week_offset: int = 0,
    duration_minutes: int = 30,
) -> list[dict]:
    """
    Возвращает для каждой из 7 дней недели флаг has_slots.
    Неделя: week_start = понедельник текущей недели + week_offset.
    """
    db = get_db()
    tz_name = db.get_timezone()
    tz = pytz.timezone(tz_name)
    today = datetime.now(tz).date()
    week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=7)
    time_min_utc = tz.localize(datetime.combine(week_start, time.min)).astimezone(timezone.utc)
    time_max_utc = tz.localize(datetime.combine(week_end, time.min)).astimezone(timezone.utc)
    busy_utc = await _fetch_busy_utc(time_min_utc, time_max_utc)
    result: list[dict] = []
    for i in range(7):
        d = week_start + timedelta(days=i)
        has = _has_any_slot(d, duration_minutes=duration_minutes, busy_utc=busy_utc)
        result.append({"date": d.isoformat(), "has_slots": has})
    return result


async def get_day_slots(
    date_str: str,
    duration_minutes: int = 30,
) -> list[str]:
    """
    Возвращает список слотов на день в таймзоне настроек.
    Каждый слот — строка "HH:MM" (локальное время).
    """
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return []
    db = get_db()
    tz_name = db.get_timezone()
    tz = pytz.timezone(tz_name)
    time_min_utc = tz.localize(datetime.combine(d, time.min)).astimezone(timezone.utc)
    time_max_utc = tz.localize(datetime.combine(d + timedelta(days=1), time.min)).astimezone(timezone.utc)
    busy_utc = await _fetch_busy_utc(time_min_utc, time_max_utc)
    slots = _iter_slots(d, duration_minutes=duration_minutes)
    slots = _filter_busy(slots, duration_minutes=duration_minutes, busy_utc=busy_utc)
    return [dt.strftime("%H:%M") for dt in slots]


def _round_down_to_30min(dt: datetime) -> datetime:
    minute = (dt.minute // 30) * 30
    return dt.replace(minute=minute, second=0, microsecond=0)


async def check_slot_available(
    date_str: str,
    time_str: str,
    duration_minutes: int,
) -> bool:
    """
    Проверяет, что слот (date_str + time_str в локальной TZ) свободен.
    time_str в формате "HH:MM".
    """
    try:
        d = date.fromisoformat(date_str)
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return False
        t = time(hour=int(parts[0]), minute=int(parts[1]))
    except (ValueError, IndexError):
        return False
    db = get_db()
    tz_name = db.get_timezone()
    tz = pytz.timezone(tz_name)
    start_local = tz.localize(datetime.combine(d, t))
    slot_start = _round_down_to_30min(start_local)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    busy_utc = await _fetch_busy_utc(start_utc, end_utc)
    if busy_utc and any(_overlaps(start_utc, end_utc, b0, b1) for (b0, b1) in busy_utc):
        return False
    slots = _iter_slots(d, duration_minutes=duration_minutes)
    slots = _filter_busy(slots, duration_minutes=duration_minutes, busy_utc=busy_utc)
    return any(s == slot_start for s in slots)
