from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# чтобы `python scripts/check_google.py` видел модули из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings
from logging_setup import setup_logging
from services.google_api import get_freebusy


def main() -> None:
    setup_logging()
    s = load_settings()
    if not s.calendar_id:
        raise SystemExit("CALENDAR_ID is not set in .env")

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=7)

    busy = get_freebusy(
        calendar_id=s.calendar_id,
        time_min_utc=now,
        time_max_utc=end,
        auth_mode=s.google_auth_mode,
        service_account_json=s.credentials_path,
        oauth_client_secrets_json=s.oauth_client_secrets_path,
        oauth_token_json=s.oauth_token_path,
    )
    print("OK")
    print(f"calendar_id={s.calendar_id}")
    print(f"auth_mode={s.google_auth_mode}")
    print(f"busy_intervals={len(busy)}")
    if busy:
        print("first:", busy[0][0].isoformat(), "->", busy[0][1].isoformat())


if __name__ == "__main__":
    main()

