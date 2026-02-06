from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DOTENV_PATH = BASE_DIR / ".env"


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    """
    Мини-парсер .env без зависимостей.
    Поддерживает: KEY=VALUE, комментарии (#), пустые строки, кавычки ""/''.
    """
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "=" not in s:
        return None
    key, value = s.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return key, value


def load_dotenv(path: Path = DEFAULT_DOTENV_PATH, *, override: bool = False) -> None:
    """
    Загружает переменные окружения из .env, если файл существует.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(raw)
        if not parsed:
            continue
        key, value = parsed
        if override or key not in os.environ:
            os.environ[key] = value


def _require(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _as_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except ValueError as e:
        raise RuntimeError(f"Invalid int env var {name}={v!r}") from e


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int

    # Google Calendar
    calendar_id: Optional[str]
    credentials_path: Path
    google_auth_mode: str  # "oauth" | "service_account"
    oauth_client_secrets_path: Path
    oauth_token_path: Path

    # Scheduling defaults
    timezone: str
    work_start: str  # "HH:MM"
    work_end: str  # "HH:MM"
    buffer_hours: int

    # Storage
    db_path: Path

    # Automation
    pending_ttl_hours: int
    expire_check_interval_seconds: int

    # Mini App (URL для кнопки «Открыть приложение» в боте)
    bot_webapp_url: Optional[str] = None


def load_settings(*, dotenv_path: Path = DEFAULT_DOTENV_PATH) -> Settings:
    """
    Единая точка загрузки настроек.
    """
    # Для локальной разработки ожидаем, что `.env` имеет приоритет над текущим окружением,
    # иначе можно легко «поймать» старые экспортированные переменные из shell.
    load_dotenv(dotenv_path, override=True)

    bot_token = _require("BOT_TOKEN")
    admin_id = _as_int("ADMIN_ID", default=0)
    if admin_id <= 0:
        raise RuntimeError("ADMIN_ID must be a positive integer")

    calendar_id = os.getenv("CALENDAR_ID") or None
    credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH") or (BASE_DIR / "credentials.json"))
    # По умолчанию оставляем legacy Service Account (чтобы не ломать существующий запуск).
    # Для нового режима выставь GOOGLE_AUTH_MODE=oauth и положи client_secrets.json + token.json.
    google_auth_mode = (os.getenv("GOOGLE_AUTH_MODE") or "service_account").strip().lower()
    if google_auth_mode not in ("oauth", "service_account"):
        raise RuntimeError("GOOGLE_AUTH_MODE must be 'oauth' or 'service_account'")
    oauth_client_secrets_path = Path(
        os.getenv("GOOGLE_OAUTH_CLIENT_SECRETS_PATH") or (BASE_DIR / "client_secrets.json")
    )
    oauth_token_path = Path(os.getenv("GOOGLE_OAUTH_TOKEN_PATH") or (BASE_DIR / "token.json"))

    timezone = os.getenv("TIMEZONE") or "Europe/Moscow"
    work_start = os.getenv("WORK_START") or "11:00"
    work_end = os.getenv("WORK_END") or "18:00"
    buffer_hours = _as_int("BUFFER_HOURS", default=3)

    db_path = Path(os.getenv("DB_PATH") or (BASE_DIR / "database" / "smart_scheduler.db"))
    pending_ttl_hours = _as_int("PENDING_TTL_HOURS", default=24)
    expire_check_interval_seconds = _as_int("EXPIRE_CHECK_INTERVAL_SECONDS", default=60)

    bot_webapp_url = (os.getenv("BOT_WEBAPP_URL") or "").strip() or None

    return Settings(
        bot_token=bot_token,
        admin_id=admin_id,
        bot_webapp_url=bot_webapp_url,
        calendar_id=calendar_id,
        credentials_path=credentials_path,
        google_auth_mode=google_auth_mode,
        oauth_client_secrets_path=oauth_client_secrets_path,
        oauth_token_path=oauth_token_path,
        timezone=timezone,
        work_start=work_start,
        work_end=work_end,
        buffer_hours=buffer_hours,
        db_path=db_path,
        pending_ttl_hours=pending_ttl_hours,
        expire_check_interval_seconds=expire_check_interval_seconds,
    )

