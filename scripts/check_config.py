from __future__ import annotations

import sys
from pathlib import Path

# чтобы `python scripts/check_config.py` видел модули из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings
from logging_setup import setup_logging


def main() -> None:
    setup_logging()
    s = load_settings()
    # Не печатаем токен.
    print("OK")
    print(f"ADMIN_ID={s.admin_id}")
    print(f"TIMEZONE={s.timezone}")
    print(f"DB_PATH={s.db_path}")
    print(f"GOOGLE_AUTH_MODE={s.google_auth_mode}")
    print(f"GOOGLE_CREDENTIALS_PATH={s.credentials_path}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRETS_PATH={s.oauth_client_secrets_path}")
    print(f"GOOGLE_OAUTH_TOKEN_PATH={s.oauth_token_path}")
    print(f"CALENDAR_ID={s.calendar_id}")


if __name__ == "__main__":
    main()

