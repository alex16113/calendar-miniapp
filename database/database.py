from __future__ import annotations

import logging
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Generator, Iterable, Optional, TypedDict, Any

import pytz


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "smart_scheduler.db"

logger = logging.getLogger(__name__)

# ключи настроек в таблице `settings`
SETTING_TIMEZONE = "timezone"
SETTING_WORK_START = "work_start"  # "HH:MM"
SETTING_WORK_END = "work_end"  # "HH:MM"
SETTING_BUFFER_HOURS = "buffer_hours"  # int (string in DB)
SETTING_WORK_SCHEDULE = "work_schedule"  # JSON, per-weekday


class WorkDay(TypedDict, total=False):
    enabled: bool
    start: str  # "HH:MM"
    end: str  # "HH:MM"


WorkSchedule = Dict[str, WorkDay]  # weekday "0".."6"


def _utc_now() -> datetime:
    """Текущее время в UTC (aware)."""
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime, tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """
    Конвертация даты в UTC c учётом pytz-таймзоны.

    - если dt naive и tz задана -> локализуем и переводим в UTC;
    - если dt naive и tz не задана -> считаем, что dt уже UTC;
    - если dt aware -> переводим в UTC.
    """
    if dt.tzinfo is None:
        if tz is not None:
            localized = tz.localize(dt)
            return localized.astimezone(timezone.utc)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dt_to_str(dt: datetime) -> str:
    """Сериализация datetime в ISO-строку в UTC."""
    return _to_utc(dt).isoformat()


def _str_to_dt(value: str) -> datetime:
    """Обратная операция: ISO-строка -> datetime с tzinfo=UTC."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class Meeting:
    id: Optional[int]
    user_id: int
    username: Optional[str]
    user_name: Optional[str]
    user_email: Optional[str]
    subject: Optional[str]
    description: Optional[str]
    start_time: datetime
    duration: int  # в минутах
    status: str
    created_at: datetime
    google_event_id: Optional[str] = None
    google_event_html_link: Optional[str] = None
    google_meet_link: Optional[str] = None


class Database:
    """
    Обёртка над SQLite с минимальным набором операций под наше ТЗ.
    """

    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- schema ---

    def init_schema(self) -> None:
        """
        Создаёт таблицы, если их ещё нет.

        Соответствует разделу 7 ТЗ:
        - settings(key, value)
        - meetings(...)
        - blacklist_dates(date, reason)
        - users_blacklisted(user_id, banned_at)
        """
        logger.info("Initializing SQLite schema", extra={"db_path": str(self.path)})
        with self.get_conn() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    user_name TEXT,
                    user_email TEXT,
                    subject TEXT,
                    description TEXT,
                    start_time TEXT NOT NULL,  -- ISO UTC
                    duration INTEGER NOT NULL, -- минуты
                    status TEXT NOT NULL,      -- pending/confirmed/rejected/expired
                    created_at TEXT NOT NULL   -- ISO UTC
                )
                """
            )
            self._migrate_meetings_columns(conn)

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS blacklist_dates (
                    date TEXT PRIMARY KEY, -- YYYY-MM-DD (UTC)
                    reason TEXT
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users_blacklisted (
                    user_id INTEGER PRIMARY KEY,
                    banned_at TEXT NOT NULL -- ISO UTC
                )
                """
            )

    def _migrate_meetings_columns(self, conn: sqlite3.Connection) -> None:
        """
        Мягкая миграция таблицы `meetings`.

        Важно:
        - ALTER TABLE ADD COLUMN в SQLite безопасен для существующих строк (NULL дефолт).
        - Это позволяет докатывать фичи без отдельного migration framework.
        """
        try:
            cur = conn.execute("PRAGMA table_info(meetings)")
            existing = {str(r["name"]) for r in cur.fetchall()}
        except Exception:
            logger.exception("Failed to read PRAGMA table_info(meetings)")
            return

        desired: dict[str, str] = {
            "google_event_id": "TEXT",
            "google_event_html_link": "TEXT",
            "google_meet_link": "TEXT",
        }
        added: list[str] = []
        for col, col_type in desired.items():
            if col in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE meetings ADD COLUMN {col} {col_type}")
            except Exception:
                logger.exception("Failed to ALTER TABLE meetings ADD COLUMN", extra={"column": col, "type": col_type})
                continue
            added.append(col)

        if added:
            logger.info("DB migration applied: meetings columns added", extra={"added": added})

    @staticmethod
    def _row_to_meeting(row: sqlite3.Row) -> Meeting:
        keys = set(row.keys())
        return Meeting(
            id=row["id"],
            user_id=row["user_id"],
            username=row["username"],
            user_name=row["user_name"],
            user_email=row["user_email"],
            subject=row["subject"],
            description=row["description"],
            start_time=_str_to_dt(row["start_time"]),
            duration=row["duration"],
            status=row["status"],
            created_at=_str_to_dt(row["created_at"]),
            google_event_id=(row["google_event_id"] if "google_event_id" in keys else None),
            google_event_html_link=(row["google_event_html_link"] if "google_event_html_link" in keys else None),
            google_meet_link=(row["google_meet_link"] if "google_meet_link" in keys else None),
        )

    # --- settings ---

    def set_setting(self, key: str, value: str) -> None:
        logger.info("Setting updated", extra={"key": key})
        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.get_conn() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            if row is None:
                return default
            return str(row["value"])

    def get_all_settings(self) -> Dict[str, str]:
        with self.get_conn() as conn:
            cur = conn.execute("SELECT key, value FROM settings")
            return {str(row["key"]): str(row["value"]) for row in cur.fetchall()}

    def bootstrap_settings(
        self,
        *,
        timezone: str = "Europe/Moscow",
        work_start: str = "11:00",
        work_end: str = "18:00",
        buffer_hours: int = 3,
    ) -> Dict[str, str]:
        """
        Записывает дефолтные настройки в `settings`, только если ключей ещё нет.

        Важно: НЕ перезаписывает существующие значения.
        Возвращает словарь фактически добавленных (key -> value).
        """
        schedule_default: WorkSchedule = {
            # Пн–Пт: рабочие часы из старых ключей
            "0": {"enabled": True, "start": work_start, "end": work_end},
            "1": {"enabled": True, "start": work_start, "end": work_end},
            "2": {"enabled": True, "start": work_start, "end": work_end},
            "3": {"enabled": True, "start": work_start, "end": work_end},
            "4": {"enabled": True, "start": work_start, "end": work_end},
            # Сб/Вс: выходные по умолчанию
            "5": {"enabled": False},
            "6": {"enabled": False},
        }

        defaults: Dict[str, str] = {
            SETTING_TIMEZONE: timezone,
            SETTING_WORK_START: work_start,
            SETTING_WORK_END: work_end,
            SETTING_BUFFER_HOURS: str(int(buffer_hours)),
            SETTING_WORK_SCHEDULE: json.dumps(schedule_default, ensure_ascii=False, separators=(",", ":")),
        }

        inserted: Dict[str, str] = {}
        with self.get_conn() as conn:
            cur = conn.execute("SELECT key FROM settings")
            existing = {str(r["key"]) for r in cur.fetchall()}

            for key, value in defaults.items():
                if key in existing:
                    continue
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES (?, ?)",
                    (key, value),
                )
                inserted[key] = value

        if inserted:
            logger.info("Bootstrapped default settings", extra={"inserted": inserted})
        else:
            logger.info("Default settings already present; bootstrap skipped")

        return inserted

    def get_timezone(self, default: str = "Europe/Moscow") -> str:
        return self.get_setting(SETTING_TIMEZONE, default) or default

    def get_work_hours(self, default_start: str = "11:00", default_end: str = "18:00") -> tuple[str, str]:
        start = self.get_setting(SETTING_WORK_START, default_start) or default_start
        end = self.get_setting(SETTING_WORK_END, default_end) or default_end
        return start, end

    def get_work_schedule(self) -> WorkSchedule:
        """
        Возвращает расписание по дням недели.

        Формат: ключи '0'..'6' (0=Пн), значение: {enabled, start, end}.
        Если ключ отсутствует — создаём дефолт (Пн–Пт рабочие часы из work_start/work_end, Сб/Вс выходные)
        и сохраняем в БД один раз.
        """
        raw = self.get_setting(SETTING_WORK_SCHEDULE)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    # нормализуем ключи и значения
                    normalized: WorkSchedule = {}
                    for k, v in data.items():
                        ks = str(k)
                        if ks not in {"0", "1", "2", "3", "4", "5", "6"}:
                            continue
                        if not isinstance(v, dict):
                            continue
                        enabled = bool(v.get("enabled", False))
                        day: WorkDay = {"enabled": enabled}
                        if enabled:
                            s = str(v.get("start", "")).strip()
                            e = str(v.get("end", "")).strip()
                            if s and e:
                                day["start"] = s
                                day["end"] = e
                        normalized[ks] = day
                    # ensure all days exist
                    for wd in ("0", "1", "2", "3", "4", "5", "6"):
                        normalized.setdefault(wd, {"enabled": False})
                    return normalized
            except Exception:
                logger.warning("Invalid work_schedule JSON; regenerating", extra={"raw_len": len(raw)})

        # дефолт: Пн–Пт = старые work_start/work_end, Сб/Вс = выходной
        ws, we = self.get_work_hours()
        schedule_default: WorkSchedule = {
            "0": {"enabled": True, "start": ws, "end": we},
            "1": {"enabled": True, "start": ws, "end": we},
            "2": {"enabled": True, "start": ws, "end": we},
            "3": {"enabled": True, "start": ws, "end": we},
            "4": {"enabled": True, "start": ws, "end": we},
            "5": {"enabled": False},
            "6": {"enabled": False},
        }
        self.set_setting(SETTING_WORK_SCHEDULE, json.dumps(schedule_default, ensure_ascii=False, separators=(",", ":")))
        return schedule_default

    def set_work_schedule_day(
        self,
        *,
        weekday: int,
        enabled: bool,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        """
        Обновляет один день в расписании.
        """
        if weekday < 0 or weekday > 6:
            raise ValueError("weekday must be 0..6")
        schedule = self.get_work_schedule()
        k = str(int(weekday))
        if not enabled:
            schedule[k] = {"enabled": False}
        else:
            if not start or not end:
                raise ValueError("start/end required when enabled=True")
            schedule[k] = {"enabled": True, "start": str(start), "end": str(end)}
        self.set_setting(SETTING_WORK_SCHEDULE, json.dumps(schedule, ensure_ascii=False, separators=(",", ":")))

    def get_work_hours_for_date(self, day) -> tuple[str, str] | None:
        """
        Рабочие часы для конкретной даты (локальная дата). None = выходной.
        """
        try:
            wd = int(day.weekday())
        except Exception:
            return None
        schedule = self.get_work_schedule()
        item = schedule.get(str(wd)) or {}
        if not item.get("enabled"):
            return None
        s = str(item.get("start") or "").strip()
        e = str(item.get("end") or "").strip()
        if not s or not e:
            return None
        return s, e

    def get_buffer_hours(self, default: int = 3) -> int:
        raw = self.get_setting(SETTING_BUFFER_HOURS, str(default)) or str(default)
        try:
            return int(raw)
        except ValueError:
            logger.warning("Invalid buffer_hours in DB; using default", extra={"raw": raw, "default": default})
            return default

    def set_timezone(self, tz_name: str) -> None:
        self.set_setting(SETTING_TIMEZONE, tz_name)

    def set_work_hours(self, start_hhmm: str, end_hhmm: str) -> None:
        self.set_setting(SETTING_WORK_START, start_hhmm)
        self.set_setting(SETTING_WORK_END, end_hhmm)

    def set_buffer_hours(self, hours: int) -> None:
        self.set_setting(SETTING_BUFFER_HOURS, str(int(hours)))

    # --- meetings ---

    def create_meeting(
        self,
        *,
        user_id: int,
        username: Optional[str],
        user_name: Optional[str],
        user_email: Optional[str],
        subject: Optional[str],
        description: Optional[str],
        start_time: datetime,
        duration_minutes: int,
        status: str = "pending",
        timezone_name: str = "UTC",
    ) -> int:
        """
        Создать запись встречи в статусе pending (по умолчанию).

        Все времена в БД — в UTC.
        """
        tz = pytz.timezone(timezone_name)
        start_utc = _to_utc(start_time, tz)
        created_at = _utc_now()

        logger.info(
            "Creating meeting",
            extra={
                "user_id": user_id,
                "username": username,
                "start_time_utc": _dt_to_str(start_utc),
                "duration_minutes": duration_minutes,
                "status": status,
            },
        )
        with self.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO meetings (
                    user_id, username, user_name, user_email,
                    subject, description,
                    start_time, duration, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    user_name,
                    user_email,
                    subject,
                    description,
                    _dt_to_str(start_utc),
                    duration_minutes,
                    status,
                    _dt_to_str(created_at),
                ),
            )
            return int(cur.lastrowid)

    def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        with self.get_conn() as conn:
            cur = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
            row = cur.fetchone()
            if row is None:
                return None
            return self._row_to_meeting(row)

    def update_meeting_status(self, meeting_id: int, status: str) -> None:
        logger.info("Meeting status update", extra={"meeting_id": meeting_id, "status": status})
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE meetings SET status = ? WHERE id = ?",
                (status, meeting_id),
            )

    def set_meeting_google_event(
        self,
        meeting_id: int,
        *,
        event_id: str | None,
        html_link: str | None,
        meet_link: str | None,
    ) -> None:
        logger.info(
            "Meeting google event updated",
            extra={
                "meeting_id": meeting_id,
                "google_event_id": event_id,
                "has_html_link": bool(html_link),
                "has_meet_link": bool(meet_link),
            },
        )
        with self.get_conn() as conn:
            conn.execute(
                """
                UPDATE meetings
                SET google_event_id = ?, google_event_html_link = ?, google_meet_link = ?
                WHERE id = ?
                """,
                (event_id, html_link, meet_link, meeting_id),
            )

    def expire_old_pending(self, ttl_hours: int = 24) -> int:
        """
        Переводит старые pending-заявки в статус expired.
        Возвращает количество обновлённых строк.
        """
        expired = self.expire_old_pending_with_list(ttl_hours=ttl_hours)
        return len(expired)

    def expire_old_pending_with_list(self, ttl_hours: int = 24) -> list[Meeting]:
        """
        Переводит старые pending-заявки в статус expired и возвращает список истекших заявок.
        """
        threshold = _utc_now() - timedelta(hours=ttl_hours)
        threshold_s = _dt_to_str(threshold)
        with self.get_conn() as conn:
            cur = conn.execute(
                "SELECT * FROM meetings WHERE status = 'pending' AND created_at < ?",
                (threshold_s,),
            )
            rows = cur.fetchall()
            if not rows:
                return []

            meetings: list[Meeting] = [self._row_to_meeting(row) for row in rows]

            ids = [m.id for m in meetings if m.id is not None]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"UPDATE meetings SET status = 'expired' WHERE id IN ({placeholders})",
                tuple(ids),
            )
            logger.info(
                "Expired old pending meetings",
                extra={"ttl_hours": ttl_hours, "expired_count": len(ids)},
            )
            return meetings

    def iter_meetings_by_status(
        self,
        statuses: Iterable[str],
    ) -> Iterable[Meeting]:
        placeholders = ",".join("?" for _ in statuses)
        if not placeholders:
            return []

        with self.get_conn() as conn:
            cur = conn.execute(
                f"SELECT * FROM meetings WHERE status IN ({placeholders})",
                tuple(statuses),
            )
            for row in cur:
                yield self._row_to_meeting(row)

    def count_pending_meetings(self) -> int:
        with self.get_conn() as conn:
            cur = conn.execute("SELECT COUNT(1) AS cnt FROM meetings WHERE status = 'pending'")
            row = cur.fetchone()
            return int(row["cnt"] if row else 0)

    def list_pending_meetings(self, *, limit: int, offset: int = 0) -> list[Meeting]:
        """
        Возвращает pending-заявки, отсортированные по created_at ASC (старые сверху).
        """
        with self.get_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM meetings
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
                """,
                (int(limit), int(offset)),
            )
            rows = cur.fetchall()
            return [self._row_to_meeting(r) for r in rows]

    def get_last_meeting_by_user(self, user_id: int) -> Optional[Meeting]:
        """
        Последняя заявка пользователя (по created_at DESC), где есть email.
        """
        with self.get_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM meetings
                WHERE user_id = ?
                  AND user_email IS NOT NULL
                  AND TRIM(user_email) != ''
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
            return self._row_to_meeting(row) if row is not None else None

    def count_user_meetings(self, *, user_id: int, statuses: Iterable[str]) -> int:
        statuses_l = [str(s) for s in statuses]
        placeholders = ",".join("?" for _ in statuses_l)
        if not placeholders:
            return 0
        with self.get_conn() as conn:
            cur = conn.execute(
                f"SELECT COUNT(1) AS cnt FROM meetings WHERE user_id = ? AND status IN ({placeholders})",
                (int(user_id), *statuses_l),
            )
            row = cur.fetchone()
            return int(row["cnt"] if row else 0)

    def list_user_meetings(
        self,
        *,
        user_id: int,
        statuses: Iterable[str],
        limit: int,
        offset: int = 0,
    ) -> list[Meeting]:
        statuses_l = [str(s) for s in statuses]
        placeholders = ",".join("?" for _ in statuses_l)
        if not placeholders:
            return []
        with self.get_conn() as conn:
            cur = conn.execute(
                f"""
                SELECT * FROM meetings
                WHERE user_id = ?
                  AND status IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (int(user_id), *statuses_l, int(limit), int(offset)),
            )
            rows = cur.fetchall()
            return [self._row_to_meeting(r) for r in rows]

    def update_meeting_status_if_current(self, meeting_id: int, *, from_status: str, to_status: str) -> bool:
        """
        Атомарное обновление статуса: меняем только если текущий статус совпадает.
        Возвращает True если реально обновили.
        """
        logger.info(
            "Meeting status conditional update",
            extra={"meeting_id": meeting_id, "from_status": from_status, "to_status": to_status},
        )
        with self.get_conn() as conn:
            cur = conn.execute(
                "UPDATE meetings SET status = ? WHERE id = ? AND status = ?",
                (str(to_status), int(meeting_id), str(from_status)),
            )
            return bool(cur.rowcount)

    def list_meetings_in_time_range(
        self,
        *,
        status: str,
        start_time_min_utc: datetime,
        start_time_max_utc: datetime,
        limit: int = 1000,
    ) -> list[Meeting]:
        """
        Список встреч по статусу и диапазону start_time (UTC), полуинтервал [min, max).
        """
        start_s = _dt_to_str(start_time_min_utc)
        end_s = _dt_to_str(start_time_max_utc)
        with self.get_conn() as conn:
            cur = conn.execute(
                """
                SELECT * FROM meetings
                WHERE status = ? AND start_time >= ? AND start_time < ?
                ORDER BY start_time ASC
                LIMIT ?
                """,
                (status, start_s, end_s, int(limit)),
            )
            rows = cur.fetchall()
            return [
                self._row_to_meeting(row) for row in rows
            ]

    # --- blacklists ---

    def add_blacklist_date(self, date_str: str, reason: Optional[str] = None) -> None:
        """
        Добавляет дату в blacklist.

        Формат date_str: 'YYYY-MM-DD' (UTC).
        """
        logger.info("Blacklist date added", extra={"date": date_str})
        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO blacklist_dates(date, reason)
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET reason = excluded.reason
                """,
                (date_str, reason),
            )

    def remove_blacklist_date(self, date_str: str) -> bool:
        logger.info("Blacklist date removed", extra={"date": date_str})
        with self.get_conn() as conn:
            cur = conn.execute("DELETE FROM blacklist_dates WHERE date = ?", (date_str,))
            return bool(cur.rowcount)

    def list_blacklist_dates(self, limit: int = 50) -> list[tuple[str, Optional[str]]]:
        with self.get_conn() as conn:
            cur = conn.execute(
                "SELECT date, reason FROM blacklist_dates ORDER BY date ASC LIMIT ?",
                (int(limit),),
            )
            return [(str(r["date"]), r["reason"]) for r in cur.fetchall()]

    def is_date_blacklisted(self, date_str: str) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM blacklist_dates WHERE date = ? LIMIT 1",
                (date_str,),
            )
            return cur.fetchone() is not None

    def blacklist_user(self, user_id: int) -> None:
        logger.info("User blacklisted", extra={"user_id": user_id})
        with self.get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users_blacklisted(user_id, banned_at)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET banned_at = excluded.banned_at
                """,
                (user_id, _dt_to_str(_utc_now())),
            )

    def unblacklist_user(self, user_id: int) -> None:
        logger.info("User unblacklisted", extra={"user_id": user_id})
        with self.get_conn() as conn:
            conn.execute("DELETE FROM users_blacklisted WHERE user_id = ?", (user_id,))

    def list_banned_users(self, limit: int = 200) -> list[tuple[int, str, Optional[str], Optional[str]]]:
        """Возвращает (user_id, banned_at_iso, username, user_name) из users_blacklisted + последняя встреча для отображения."""
        with self.get_conn() as conn:
            cur = conn.execute(
                """
                SELECT b.user_id, b.banned_at,
                    (SELECT m.username FROM meetings m WHERE m.user_id = b.user_id ORDER BY m.created_at DESC LIMIT 1),
                    (SELECT m.user_name FROM meetings m WHERE m.user_id = b.user_id ORDER BY m.created_at DESC LIMIT 1)
                FROM users_blacklisted b
                ORDER BY b.banned_at DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            return [
                (row["user_id"], row["banned_at"], row[2], row[3])
                for row in cur.fetchall()
            ]

    def is_user_blacklisted(self, user_id: int) -> bool:
        with self.get_conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM users_blacklisted WHERE user_id = ? LIMIT 1",
                (user_id,),
            )
            return cur.fetchone() is not None


_db_singleton: Optional[Database] = None


def get_db() -> Database:
    """
    Ленивая инициализация singleton-объекта БД.
    Удобно дергать из хендлеров без DI на первом этапе.
    """
    global _db_singleton
    if _db_singleton is None:
        _db_singleton = Database()
        _db_singleton.init_schema()
    return _db_singleton


def init_db(path: Optional[Path] = None) -> Database:
    """
    Явная инициализация БД (например, из entrypoint).
    """
    db = Database(path or DB_PATH)
    db.init_schema()
    global _db_singleton
    _db_singleton = db
    return db

