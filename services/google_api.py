"""
Обёртка над Google Calendar API.

Поддерживаем 2 режима авторизации:
- service_account (legacy): credentials.json
- oauth (Desktop App): client_secrets.json + token.json (refresh_token)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Tuple

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from urllib.parse import quote
from uuid import uuid4

from services.google_calendar_service import AuthNeeded, GoogleCalendarService


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_CREDENTIALS_PATH = BASE_DIR / "credentials.json"
DEFAULT_OAUTH_CLIENT_SECRETS_PATH = BASE_DIR / "client_secrets.json"
DEFAULT_OAUTH_TOKEN_PATH = BASE_DIR / "token.json"

logger = logging.getLogger(__name__)

CAL_TEMPLATE_BASE = "https://www.google.com/calendar/render?action=TEMPLATE"


def _parse_rfc3339(value: str) -> datetime:
    # Google часто отдаёт 'Z' в конце
    v = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _to_compact_utc(dt: datetime) -> str:
    """
    Формат: YYYYMMDDTHHMMSSZ (строго UTC).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def generate_calendar_link(
    *,
    subject: str,
    start_time_utc: datetime,
    duration_min: int,
    description: str | None,
) -> str:
    """
    Генерирует Google Calendar Template Link для добавления события в календарь клиента.

    Формат:
    https://www.google.com/calendar/render?action=TEMPLATE&text={subject}&dates={start_utc}/{end_utc}&details={description}
    """
    if start_time_utc.tzinfo is None:
        start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)
    start_time_utc = start_time_utc.astimezone(timezone.utc)
    end_time_utc = start_time_utc + timedelta(minutes=int(duration_min))

    text_q = quote(subject or "Встреча", safe="")
    details_q = quote(description or "", safe="")
    dates = f"{_to_compact_utc(start_time_utc)}/{_to_compact_utc(end_time_utc)}"

    return f"{CAL_TEMPLATE_BASE}&text={text_q}&dates={dates}&details={details_q}"


def build_calendar_service(
    *,
    auth_mode: str = "service_account",
    service_account_json: Path | str = DEFAULT_CREDENTIALS_PATH,
    oauth_client_secrets_json: Path | str = DEFAULT_OAUTH_CLIENT_SECRETS_PATH,
    oauth_token_json: Path | str = DEFAULT_OAUTH_TOKEN_PATH,
    scopes: List[str] | None = None,
) -> Any:
    """
    Инициализирует Google Calendar API client.
    """
    effective_scopes = scopes or DEFAULT_SCOPES

    mode = (auth_mode or "service_account").strip().lower()
    if mode == "oauth":
        oauth = GoogleCalendarService(
            client_secrets_path=oauth_client_secrets_json,
            token_path=oauth_token_json,
            scopes=effective_scopes,
        )
        try:
            return oauth.build_service()
        except AuthNeeded as e:
            raise RuntimeError(
                "Google OAuth token is missing/expired and cannot be refreshed. "
                f"Authorize via: {e.authorization_url}"
            ) from e

    if mode != "service_account":
        raise RuntimeError("auth_mode must be 'oauth' or 'service_account'")

    json_path = Path(service_account_json)
    if not json_path.is_file():
        raise FileNotFoundError(f"Service account JSON not found: {json_path}")

    logger.info(
        "Initializing Google Calendar service account client",
        extra={"credentials_path": str(json_path), "scopes": effective_scopes},
    )
    creds = Credentials.from_service_account_file(str(json_path), scopes=effective_scopes)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def get_calendar_timezone(
    *,
    calendar_id: str,
    auth_mode: str = "service_account",
    service_account_json: Path | str = DEFAULT_CREDENTIALS_PATH,
    oauth_client_secrets_json: Path | str = DEFAULT_OAUTH_CLIENT_SECRETS_PATH,
    oauth_token_json: Path | str = DEFAULT_OAUTH_TOKEN_PATH,
) -> str | None:
    """
    Возвращает таймзону календаря (IANA), например "Europe/Moscow".
    """
    if not calendar_id:
        raise RuntimeError("CALENDAR_ID is required for get_calendar_timezone")
    service = build_calendar_service(
        auth_mode=auth_mode,
        service_account_json=service_account_json,
        oauth_client_secrets_json=oauth_client_secrets_json,
        oauth_token_json=oauth_token_json,
    )
    cal = service.calendars().get(calendarId=calendar_id).execute()
    return (cal or {}).get("timeZone")


def get_freebusy(
    *,
    calendar_id: str,
    time_min_utc: datetime,
    time_max_utc: datetime,
    auth_mode: str = "service_account",
    service_account_json: Path | str = DEFAULT_CREDENTIALS_PATH,
    oauth_client_secrets_json: Path | str = DEFAULT_OAUTH_CLIENT_SECRETS_PATH,
    oauth_token_json: Path | str = DEFAULT_OAUTH_TOKEN_PATH,
) -> List[Tuple[datetime, datetime]]:
    """
    Возвращает busy-интервалы (UTC) для календаря в диапазоне [time_min_utc, time_max_utc).
    """
    if not calendar_id:
        raise RuntimeError("CALENDAR_ID is required for freebusy")

    service = build_calendar_service(
        auth_mode=auth_mode,
        service_account_json=service_account_json,
        oauth_client_secrets_json=oauth_client_secrets_json,
        oauth_token_json=oauth_token_json,
    )
    body = {
        "timeMin": _to_rfc3339(time_min_utc),
        "timeMax": _to_rfc3339(time_max_utc),
        "items": [{"id": calendar_id}],
    }
    logger.info(
        "Google freebusy query",
        extra={"calendar_id": calendar_id, "timeMin": body["timeMin"], "timeMax": body["timeMax"]},
    )
    resp = service.freebusy().query(body=body).execute()
    calendars = (resp or {}).get("calendars", {}) or {}
    cal = calendars.get(calendar_id, {}) or {}
    busy = cal.get("busy", []) or []
    intervals: List[Tuple[datetime, datetime]] = []
    for b in busy:
        try:
            s = _parse_rfc3339(b["start"])
            e = _parse_rfc3339(b["end"])
        except Exception:
            continue
        intervals.append((s, e))
    return intervals


def create_event(
    *,
    calendar_id: str,
    start_utc: datetime,
    duration_minutes: int,
    summary: str,
    description: str | None,
    attendee_email: str | None,
    create_meet: bool = False,
    auth_mode: str = "service_account",
    service_account_json: Path | str = DEFAULT_CREDENTIALS_PATH,
    oauth_client_secrets_json: Path | str = DEFAULT_OAUTH_CLIENT_SECRETS_PATH,
    oauth_token_json: Path | str = DEFAULT_OAUTH_TOKEN_PATH,
    send_updates: str = "all",
) -> dict:
    """
    Создаёт событие в Google Calendar.
    Возвращает raw event dict (в т.ч. id/htmlLink).
    """
    if not calendar_id:
        raise RuntimeError("CALENDAR_ID is required for create_event")

    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    start_utc = start_utc.astimezone(timezone.utc)
    end_utc = start_utc + timedelta(minutes=int(duration_minutes))

    event = {
        "summary": summary,
        "description": description or "",
        "start": {"dateTime": _to_rfc3339(start_utc), "timeZone": "UTC"},
        "end": {"dateTime": _to_rfc3339(end_utc), "timeZone": "UTC"},
    }
    if attendee_email:
        event["attendees"] = [{"email": attendee_email}]
    if create_meet:
        event["conferenceData"] = {
            "createRequest": {
                "requestId": str(uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    logger.info(
        "Google create event",
        extra={"calendar_id": calendar_id, "start": event["start"]["dateTime"], "duration": duration_minutes},
    )
    service = build_calendar_service(
        auth_mode=auth_mode,
        service_account_json=service_account_json,
        oauth_client_secrets_json=oauth_client_secrets_json,
        oauth_token_json=oauth_token_json,
    )
    insert = service.events().insert(
        calendarId=calendar_id,
        body=event,
        sendUpdates=send_updates,
        **({"conferenceDataVersion": 1} if create_meet else {}),
    )
    created = insert.execute()
    try:
        logger.info(
            "Google event created",
            extra={
                "event_id": (created or {}).get("id"),
                "has_html_link": bool((created or {}).get("htmlLink")),
                "has_meet": bool((created or {}).get("hangoutLink")) or bool(((created or {}).get("conferenceData") or {}).get("entryPoints")),
            },
        )
    except Exception:
        # не блокируем — просто лог
        logger.debug("Failed to log created event details")
    return created


def delete_event(
    *,
    calendar_id: str,
    event_id: str,
    auth_mode: str = "service_account",
    service_account_json: Path | str = DEFAULT_CREDENTIALS_PATH,
    oauth_client_secrets_json: Path | str = DEFAULT_OAUTH_CLIENT_SECRETS_PATH,
    oauth_token_json: Path | str = DEFAULT_OAUTH_TOKEN_PATH,
    send_updates: str = "none",
) -> None:
    if not calendar_id:
        raise RuntimeError("CALENDAR_ID is required for delete_event")
    if not event_id:
        raise RuntimeError("event_id is required for delete_event")

    logger.info("Google delete event", extra={"calendar_id": calendar_id, "event_id": event_id})
    service = build_calendar_service(
        auth_mode=auth_mode,
        service_account_json=service_account_json,
        oauth_client_secrets_json=oauth_client_secrets_json,
        oauth_token_json=oauth_token_json,
    )
    service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates=send_updates).execute()

