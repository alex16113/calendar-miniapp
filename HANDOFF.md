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
- **Логи (структурные, сквозные)**:
  - контекст: `logging_context.py` (поля `ctx_request_id/ctx_user_id/...`), middleware: `middlewares/log_context.py`
  - формат + автоподстановка через LogRecordFactory: `logging_setup.py`
  - подключение middleware: `bot.py` (`dp.update.middleware(LogContextMiddleware())`)
- **.env**: хранит реальные значения (не коммитить).
- **.gitignore**: игнорит `credentials.json`, `client_secrets.json`, `client_secret.json`, `token.json`, `.env`, `.venv`, `*.db`, `runtime/`, `.cursor/`.
- **Анти-двойной запуск**: `bot.py` берёт файловый lock `runtime/bot.lock`, чтобы не было Telegram getUpdates conflict.

### 2) SQLite база
- Реализовано в `database/database.py`:
  - таблицы `settings`, `meetings`, `blacklist_dates`, `users_blacklisted`
  - `bootstrap_settings()` (timezone/work hours/buffer, не перетирает существующее)
  - `create_meeting()`, `get_meeting()`, `update_meeting_status()`, blacklist helpers.
  - **мягкие миграции** `meetings` через `PRAGMA table_info + ALTER TABLE ADD COLUMN`:
    - `google_event_id/google_event_html_link/google_meet_link`
  - времена в БД хранятся в **UTC (ISO строки)**.
- Дополнительно (под новые UX):
  - `get_last_meeting_by_user`, `list_user_meetings/count_user_meetings`
  - `update_meeting_status_if_current` (атомарная отмена pending)
- Скрипт: `scripts/init_db.py` инициализирует БД и дефолты из `.env`.

### 3) Telegram бот (aiogram 3.x) и флоу записи (FSM)
- Entrypoint: `bot.py`
  - `Dispatcher(storage=MemoryStorage())`
  - подключены роутеры: `common_router`, admin router, `my_requests_router`, `booking_router`, `moderation_router`
  - важно: admin router подключён **раньше** booking, чтобы `/admin` не “съедался” FSM.
  - на старте `delete_webhook()`.
- Хендлеры:
  - `handlers/common.py`: `/start`, `/help` + главное меню (**«Записаться» + «Мои заявки»**) и скрытие `/admin` для не-админа.
  - `handlers/states.py`: `BookingFSM`.
  - `handlers/booking.py`: полный MVP флоу:
    - `/book` → длительность (15/30/60/90)
    - выбор даты по неделям (✅ там, где есть слоты)
    - выбор времени (слоты шаг 30 мин)
    - анкета: имя → тема → описание (можно пропустить) → email (валидация)
    - **remember email**: если был email в прошлой заявке — предлагает “использовать/ввести другой”
    - создаёт `meetings.status=pending` и уведомляет админа.
    - `/cancel` на любом шаге.
  - `handlers/my_requests.py`:
    - `/my` + кнопка “Мои заявки”
    - список `pending+confirmed`, пагинация
    - отмена pending пользователем (status `cancelled`) + уведомление админа
    - “Новая заявка (как прошлый раз)” (шаблон: duration/subject/description/email из последней заявки)

### 4) Админ-модерация
- `handlers/moderation.py`:
  - inline кнопки: ✅ подтвердить / ❌ отклонить / 🚫 в бан (каждая на своей строке)
  - обновляет статус в БД, банит пользователя, уведомляет пользователя в чат.
  - после confirm/reject/ban автоматически присылает админу следующую pending (если есть), чтобы модерировать “потоком”.

### 5) Админка `/admin`
- `handlers/admin.py`:
  - timezone, work_schedule по дням, buffer, blacklist dates, broadcast
  - **pending list**: “Список ожидания (pending)” с пагинацией и быстрыми действиями (confirm/reject/ban + карточка)

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
> Важно: Meet-ссылку мы **не показываем в чат** (ни строкой, ни кнопкой), но храним в БД (`google_meet_link`) на будущее.

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

## Деплой на Railway (важные нюансы)
- **Секреты не в репо**: `credentials.json/client_secret*.json/token.json` игнорируются. На Railway их нужно **передать как переменные** и **создать файлы на старте** (см. ниже) или использовать Railway volumes.\n+- **SQLite**: локально путь `DB_PATH=database/smart_scheduler.db`. На Railway нужен **persistent volume** и `DB_PATH` указывать в маунт (иначе данные теряются при redeploy).\n+- **Команда старта**: `python bot.py`.\n+\n+Практичный вариант без volume для секретов:\n+- завести переменные `GOOGLE_CREDENTIALS_JSON` (или `GOOGLE_OAUTH_CLIENT_SECRET_JSON`, `GOOGLE_OAUTH_TOKEN_JSON`) и в Start Command перед запуском сделать `printf '%s' \"$GOOGLE_CREDENTIALS_JSON\" > credentials.json` (аналогично для `token.json`).\n+\n+Обязательные env на Railway: `BOT_TOKEN`, `ADMIN_ID`, `CALENDAR_ID`, `GOOGLE_AUTH_MODE`, `TIMEZONE`, `DB_PATH`, `LOG_LEVEL` и файлы/переменные для auth.\n+
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

## Prompt для следующего агента (копипаст)
Скопируй этот блок в новый агент:

```
Ты работаешь с проектом Smart Scheduler (Telegram bot на aiogram 3.x). Прочитай сначала:
- HANDOFF.md (контекст и как запускать)
- PROJECT_STEPS.md (этапы/что уже сделано)

Ключевые файлы логики:
- bot.py — entrypoint, порядок роутеров, фоновая задача expire pending, log middleware
- config.py + app_context.py — env и настройки
- database/database.py — SQLite, UTC, мягкие миграции, meeting/user queries, статусные операции
- handlers/booking.py — FSM записи, freebusy слоты, remember email, создание pending + уведомление админа
- handlers/moderation.py — confirm/reject/ban, freebusy anti-race перед confirm, create_event, сохранение google_event_* в БД, авто “следующая pending”
- handlers/admin.py — /admin меню, pending list, blacklist/broadcast/timezone/work_schedule
- handlers/my_requests.py — /my (pending+confirmed), отмена pending пользователем, “новая заявка по шаблону”
- services/google_api.py — freebusy/create_event/delete_event, оба auth режима, логирование event created
- services/google_calendar_service.py — OAuth token load/refresh/save, auth URL
- services/meeting_formatter.py — единые тексты сообщений (Meet не показываем)
- logging_context.py / middlewares/log_context.py / logging_setup.py — структурные логи (ctx_*)

Инварианты:
- время в БД UTC, отображение в timezone из settings
- secrets (credentials/token) не коммитятся, на деплое их нужно доставлять в runtime

Задача: <вставь текущую задачу>
```

