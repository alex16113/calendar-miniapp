"""
Админские эндпоинты API. Все требуют get_telegram_admin_id (user_id == ADMIN_ID).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_telegram_admin_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _extract_meet_link(event: dict) -> str | None:
    link = (event or {}).get("hangoutLink")
    if link:
        return str(link)
    conf = (event or {}).get("conferenceData") or {}
    for ep in conf.get("entryPoints") or []:
        if isinstance(ep, dict) and ep.get("uri"):
            return str(ep["uri"])
    return None


# --- Settings ---


@router.get("/settings")
async def admin_get_settings(_admin_id: int = Depends(get_telegram_admin_id)):
    """Таймзона, work_schedule, buffer_hours, blacklist дат."""
    from database import get_db
    db = get_db()
    tz = db.get_timezone()
    buffer = db.get_buffer_hours()
    work_schedule = db.get_work_schedule()
    blacklist = db.list_blacklist_dates(limit=500)
    return {
        "timezone": tz,
        "buffer_hours": buffer,
        "work_schedule": work_schedule,
        "blacklist_dates": [{"date": d, "reason": r} for d, r in blacklist],
    }


class PutTimezoneBody(BaseModel):
    timezone: str = Field(..., min_length=1, max_length=80)


@router.put("/settings/timezone")
async def admin_put_timezone(
    body: PutTimezoneBody,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    get_db().set_timezone(body.timezone.strip())
    return {"ok": True}


class PutBufferBody(BaseModel):
    buffer_hours: int = Field(..., ge=0, le=24)


@router.put("/settings/buffer_hours")
async def admin_put_buffer(
    body: PutBufferBody,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    get_db().set_buffer_hours(body.buffer_hours)
    return {"ok": True}


class WorkDaySchema(BaseModel):
    enabled: bool = False
    start: str | None = None
    end: str | None = None


class PutWorkScheduleBody(BaseModel):
    work_schedule: dict[str, WorkDaySchema]


@router.put("/settings/work_schedule")
async def admin_put_work_schedule(
    body: PutWorkScheduleBody,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    db = get_db()
    for k, v in body.work_schedule.items():
        if k not in ("0", "1", "2", "3", "4", "5", "6"):
            continue
        weekday = int(k)
        start = (v.start or "").strip() if v.enabled else None
        end = (v.end or "").strip() if v.enabled else None
        db.set_work_schedule_day(weekday=weekday, enabled=v.enabled, start=start, end=end)
    return {"ok": True}


class PostBlacklistBody(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str | None = None


@router.post("/settings/blacklist")
async def admin_add_blacklist(
    body: PostBlacklistBody,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    get_db().add_blacklist_date(body.date, reason=body.reason)
    return {"ok": True}


@router.delete("/settings/blacklist/{date_str}")
async def admin_remove_blacklist(
    date_str: str,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    if len(date_str) != 10 or date_str.count("-") != 2:
        raise HTTPException(status_code=400, detail="Invalid date, use YYYY-MM-DD")
    removed = get_db().remove_blacklist_date(date_str)
    return {"ok": True, "removed": removed}


# --- Pending ---


@router.get("/pending")
async def admin_pending(
    _admin_id: int = Depends(get_telegram_admin_id),
    page: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
):
    """Список pending-заявок с пагинацией."""
    from database import get_db
    from services.meeting_formatter import format_local_datetime
    db = get_db()
    total = db.count_pending_meetings()
    total_pages = max(1, (total + limit - 1) // limit)
    page_i = min(max(0, page), total_pages - 1)
    offset = page_i * limit
    meetings = db.list_pending_meetings(limit=limit, offset=offset)
    tz_name = db.get_timezone()
    items = []
    for m in meetings:
        start_utc = m.start_time
        if start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)
        items.append({
            "id": m.id,
            "user_id": m.user_id,
            "user_name": (m.user_name or "").strip() or None,
            "user_email": (m.user_email or "").strip() or None,
            "subject": (m.subject or "").strip() or None,
            "description": (m.description or "").strip() or None,
            "start_time_utc": start_utc.isoformat(),
            "start_local": format_local_datetime(start_utc, tz_name),
            "duration": m.duration,
        })
    return {"total": total, "page": page_i, "limit": limit, "total_pages": total_pages, "items": items}


# --- Confirm / Reject / Ban ---


@router.post("/meetings/{meeting_id}/confirm")
async def admin_meeting_confirm(
    meeting_id: int,
  _admin_id: int = Depends(get_telegram_admin_id),
):
    """Подтвердить заявку: freebusy, create_event в Google, статус confirmed, уведомление пользователю."""
    from database import get_db
    from app_context import get_settings
    from services.google_api import get_freebusy, create_event
    from services.meeting_formatter import format_user_confirmed
    from aiogram import Bot

    db = get_db()
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.status != "pending":
        raise HTTPException(status_code=400, detail=f"Meeting not pending (status={meeting.status})")

    settings = get_settings()
    if not settings.calendar_id:
        raise HTTPException(status_code=503, detail="CALENDAR_ID not configured")

    start_utc = meeting.start_time
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(minutes=meeting.duration)

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
    if busy and any(_overlaps(start_utc, end_utc, b0, b1) for (b0, b1) in busy):
        raise HTTPException(status_code=409, detail="Slot is busy in calendar")

    use_oauth = settings.google_auth_mode == "oauth"
    desc = (meeting.description or "").strip()
    if meeting.user_email:
        desc = (desc + "\n\n" if desc else "") + f"Email клиента: {meeting.user_email}"
    try:
        created = await asyncio.to_thread(
            create_event,
            calendar_id=settings.calendar_id,
            start_utc=start_utc,
            duration_minutes=meeting.duration,
            summary=(meeting.subject or "").strip() or "Встреча",
            description=desc,
            attendee_email=meeting.user_email if use_oauth else None,
            create_meet=use_oauth,
            auth_mode=settings.google_auth_mode,
            service_account_json=settings.credentials_path,
            oauth_client_secrets_json=settings.oauth_client_secrets_path,
            oauth_token_json=settings.oauth_token_path,
            send_updates="all" if use_oauth else "none",
        )
    except Exception as e:
        logger.exception("Google create_event failed", extra={"meeting_id": meeting_id})
        raise HTTPException(status_code=502, detail="Failed to create calendar event") from e

    created = created or {}
    eid = created.get("id")
    hlink = created.get("htmlLink")
    mlink = _extract_meet_link(created)
    db.set_meeting_google_event(
        meeting_id,
        event_id=str(eid) if eid else None,
        html_link=str(hlink) if hlink else None,
        meet_link=str(mlink) if mlink else None,
    )
    db.update_meeting_status(meeting_id, "confirmed")
    meeting = db.get_meeting(meeting_id)
    tz_name = db.get_timezone()
    try:
        bot = Bot(token=settings.bot_token)
        await bot.send_message(
            meeting.user_id,
            format_user_confirmed(meeting, tz_name=tz_name),
        )
        await bot.session.close()
    except Exception:
        logger.exception("Failed to notify user", extra={"meeting_id": meeting_id})
    return {"ok": True}


class RejectBody(BaseModel):
    reason: str | None = None


@router.post("/meetings/{meeting_id}/reject")
async def admin_meeting_reject(
    meeting_id: int,
    body: RejectBody | None = None,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    from services.meeting_formatter import format_user_rejected
    from aiogram import Bot
    from app_context import get_settings

    db = get_db()
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.status != "pending":
        raise HTTPException(status_code=400, detail=f"Meeting not pending")
    reason = (body.reason or "").strip() if body else None
    db.update_meeting_status(meeting_id, "rejected")
    tz_name = db.get_timezone()
    try:
        bot = Bot(token=get_settings().bot_token)
        await bot.send_message(
            meeting.user_id,
            format_user_rejected(meeting, tz_name=tz_name, reason=reason),
        )
        await bot.session.close()
    except Exception:
        logger.exception("Failed to notify user", extra={"meeting_id": meeting_id})
    return {"ok": True}


@router.post("/meetings/{meeting_id}/ban")
async def admin_meeting_ban(
    meeting_id: int,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    from database import get_db
    from services.meeting_formatter import format_user_banned
    from aiogram import Bot
    from app_context import get_settings

    db = get_db()
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if meeting.status != "pending":
        raise HTTPException(status_code=400, detail=f"Meeting not pending")
    db.update_meeting_status(meeting_id, "rejected")
    db.blacklist_user(meeting.user_id)
    tz_name = db.get_timezone()
    try:
        bot = Bot(token=get_settings().bot_token)
        await bot.send_message(
            meeting.user_id,
            format_user_banned(meeting, tz_name=tz_name),
        )
        await bot.session.close()
    except Exception:
        logger.exception("Failed to notify user", extra={"meeting_id": meeting_id})
    return {"ok": True}


# --- Broadcast ---


class BroadcastBody(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    text: str = Field(..., min_length=1, max_length=3500)


@router.post("/broadcast")
async def admin_broadcast(
    body: BroadcastBody,
    _admin_id: int = Depends(get_telegram_admin_id),
):
    """Рассылка пользователям с подтверждёнными встречами на указанную дату."""
    from database import get_db
    from datetime import date
    from app_context import get_settings
    from aiogram import Bot

    db = get_db()
    tz_name = db.get_timezone()
    tz = __import__("pytz").timezone(tz_name)
    d = date.fromisoformat(body.date)
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
    if not user_ids:
        return {"ok": True, "sent": 0, "failed": 0, "total": 0}
    ok = 0
    fail = 0
    bot = Bot(token=get_settings().bot_token)
    try:
        for uid in user_ids:
            try:
                await bot.send_message(int(uid), body.text.strip())
                ok += 1
            except Exception:
                fail += 1
                logger.exception("Broadcast send failed", extra={"user_id": uid})
    finally:
        await bot.session.close()
    return {"ok": True, "sent": ok, "failed": fail, "total": len(user_ids)}
