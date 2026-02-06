from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# чтобы `python scripts/check_google_event.py` видел модули из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings
from logging_setup import setup_logging
from services.google_api import create_event, delete_event


def main() -> None:
    setup_logging()
    s = load_settings()
    if not s.calendar_id:
        raise SystemExit("CALENDAR_ID is not set in .env")

    start = datetime.now(timezone.utc) + timedelta(minutes=30)
    created = create_event(
        calendar_id=s.calendar_id,
        start_utc=start,
        duration_minutes=15,
        summary="Smart Scheduler TEST (auto-delete)",
        description="This event is created by scripts/check_google_event.py and will be deleted immediately.",
        attendee_email=None,
        create_meet=False,
        auth_mode=s.google_auth_mode,
        service_account_json=s.credentials_path,
        oauth_client_secrets_json=s.oauth_client_secrets_path,
        oauth_token_json=s.oauth_token_path,
        send_updates="none",
    )

    event_id = created.get("id")
    link = created.get("htmlLink")
    if not event_id:
        raise SystemExit(f"Event created but no id returned: {created}")

    delete_event(
        calendar_id=s.calendar_id,
        event_id=event_id,
        auth_mode=s.google_auth_mode,
        service_account_json=s.credentials_path,
        oauth_client_secrets_json=s.oauth_client_secrets_path,
        oauth_token_json=s.oauth_token_path,
        send_updates="none",
    )

    print("OK")
    print(f"calendar_id={s.calendar_id}")
    print(f"event_id={event_id}")
    if link:
        print(f"htmlLink={link}")


if __name__ == "__main__":
    main()

