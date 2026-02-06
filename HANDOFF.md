---
updated: 2026-02-05
project: Smart Scheduler (Telegram bot)
---

# Handoff: текущее состояние проекта

Этот файл — чтобы другой агент мог продолжить без контекста чата.

## Что уже реализовано (по факту)

### 1) Инфраструктура / конфиг / логирование
- **Config**: `config.py` читает `.env` (override=True), обязательные переменные: `BOT_TOKEN`, `ADMIN_ID`.  
  Дополнительно: `CALENDAR_ID`, `GOOGLE_AUTH_MODE`, `GOOGLE_OAUTH_CLIENT_SECRETS_PATH`, `GOOGLE_OAUTH_TOKEN_PATH`, `GOOGLE_CREDENTIALS_PATH`, `TIMEZONE`, `WORK_START/WORK_END`, `BUFFER_HOURS`, `DB_PATH`, `LOG_LEVEL`.
- **Логи**: `logging_setup.py` настраивает стандартный `logging`.
- **.env**: хранит реальные значения (не коммитить).
- **.gitignore**: игнорит `credentials.json`, `client_secrets.json`, `token.json`, `.env`, `.venv`, `*.db`.
- **Анти-двойной запуск**: `bot.py` берёт файловый lock `runtime/bot.lock`, чтобы не было Telegram getUpdates conflict.

### 2) SQLite база
- Реализовано в `database/database.py`:
  - таблицы `settings`, `meetings`, `blacklist_dates`, `users_blacklisted`
  - `bootstrap_settings()` (timezone/work hours/buffer, не перетирает существующее)
  - `create_meeting()`, `get_meeting()`, `update_meeting_status()`, blacklist helpers.
  - времена в БД хранятся в **UTC (ISO строки)**.
- Скрипт: `scripts/init_db.py` инициализирует БД и дефолты из `.env`.

### 3) Telegram бот (aiogram 3.x) и флоу записи (FSM)
- Entrypoint: `bot.py`
  - `Dispatcher(storage=MemoryStorage())`
  - подключены роутеры: `common_router`, `booking_router`, `moderation_router`, admin router.
  - на старте `delete_webhook()`.
- Хендлеры:
  - `handlers/common.py`: `/start`, `/help` + кнопка **«Записаться»**.
  - `handlers/states.py`: `BookingFSM`.
  - `handlers/booking.py`: полный MVP флоу:
    - `/book` → длительность (15/30/60/90)
    - выбор даты по неделям (✅ там, где есть слоты)
    - выбор времени (слоты шаг 30 мин)
    - анкета: имя → тема → описание (можно пропустить) → email (валидация)
    - создаёт `meetings.status=pending` и уведомляет админа.
    - `/cancel` на любом шаге.

### 4) Админ-модерация
- `handlers/moderation.py`:
  - inline кнопки: ✅ подтвердить / ❌ отклонить / 🚫 в бан (каждая на своей строке)
  - обновляет статус в БД, банит пользователя, уведомляет пользователя в чат.

## Google Calendar — текущее поведение (OAuth 2.0 + legacy Service Account)

### Настройки
- `.env`: `CALENDAR_ID=usatu.vasilyev@gmail.com`
- OAuth 2.0:
  - `client_secrets.json` лежит в корне проекта
  - `token.json` создаётся после авторизации (refresh_token внутри)
  - режим: `GOOGLE_AUTH_MODE=oauth`
- Legacy Service Account (опционально): `credentials.json` + `GOOGLE_AUTH_MODE=service_account`

### Реализовано
- `services/google_api.py`:
  - `get_freebusy(...)` используется для:
    - ✅ в неделе
    - фильтрации слотов времени на выбранный день
  - `create_event(...)` создаёт событие в календаре Алексея.
  - **Template link**: `generate_calendar_link(...)` генерит ссылку вида:
    `https://www.google.com/calendar/render?action=TEMPLATE&text=...&dates=START/END&details=...`
    где START/END: `YYYYMMDDTHHMMSSZ` (UTC), text/details url-encoded.
- Смок-тесты:
  - `scripts/check_google.py` — проверка freebusy (учитывает `GOOGLE_AUTH_MODE`)
  - `scripts/check_google_event.py` — создаёт и сразу удаляет тестовое событие (send_updates=none)
  - `scripts/google_oauth_init.py` — первичная авторизация OAuth (создаёт `token.json`)

### Поведение confirm
- `GOOGLE_AUTH_MODE=oauth`: создаём event с `attendees` + `sendUpdates=all` + генерим Google Meet (conferenceDataVersion=1).
- `GOOGLE_AUTH_MODE=service_account`: создаём event без attendees (инвайты недоступны без DWD), пользователю отдаём template link.

## Как запустить

```bash
. .venv/bin/activate
python bot.py
```

## Как протестировать Google API

```bash
. .venv/bin/activate
python scripts/check_google.py
python scripts/check_google_event.py
```

## Где смотреть план/этапы
- `PROJECT_STEPS.md` — живой роадмап, какие фазы DONE и что дальше.

## Что делать дальше (следующий логичный этап)

### PHASE 6 — Автоматизация “непротухание”
Сделать:
- периодическую задачу (без внешних либ или через APScheduler — на выбор):
  - `expire_old_pending(ttl_hours=24)` → `expired`
- UX: если заявка просрочена — админ кнопки должны отвечать “истекло/уже обработано”, пользователь — понятное сообщение.

### PHASE 7 — Редактируемая /admin-панель
Сделать:
- редактирование `settings`:
  - timezone
  - work hours
  - buffer hours
  - blacklist dates (CRUD)

### Tech debt (по желанию)
- Кэшировать `freebusy` на короткий TTL (например, 15–30 сек) чтобы не долбить API на каждый клик.
- Вынести форматирование “карточки заявки” в одну функцию.

