---
updated: 2026-02-07
project: Smart Scheduler (Telegram bot)
---

# Handoff: текущее состояние проекта

Этот файл — общее состояние бота и инфраструктуры. **Для Mini App и API (этапы 1–8, что сделано, что делать дальше)** используй **AGENT_HANDOFF.md** в корне репо — там актуальный контекст и промпт для нового агента.

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

**Только бот (как раньше):**
```bash
. .venv/bin/activate
python bot.py
```

**Бот + API в одном процессе** (для Mini App, порт 8000):
```bash
. .venv/bin/activate
python run.py
```
API: `GET /health`, `GET /`, слоты, бронирование, мои заявки. Документация: http://localhost:8000/docs

**Как проверить этап 5 (Мои заявки) без Mini App:** эндпоинты `/my/meetings` и `/my/meetings/{id}/cancel` требуют заголовок `X-Telegram-Init-Data`. Для теста сгенерируй валидную строку (только локально):
```bash
. .venv/bin/activate
INIT_DATA=$(python scripts/gen_init_data.py YOUR_TELEGRAM_USER_ID)
curl -s -H "X-Telegram-Init-Data: $INIT_DATA" "http://localhost:8000/my/meetings?page=0&limit=5"
```
В Swagger (http://localhost:8000/docs) в заголовок запроса вручную добавь `X-Telegram-Init-Data` со значением `$INIT_DATA`. Для отмены: `POST /my/meetings/{id}/cancel` с тем же заголовком.

**Проверка этапа 6 (Mini App):** в папке `mini-app/` — `npm install && npm run dev`. Локально откроется без initData (API будет 401). Чтобы проверить «Мои заявки» из приложения: раздай собранный `mini-app/dist/` по тому же домену, что и API (calendar.vpncfo.ru), и открой бота в Telegram → Menu Button — тогда initData будет валидным и список заявок подтянется.

## Как протестировать Google API

```bash
. .venv/bin/activate
python scripts/check_google.py
python scripts/check_google_event.py
```

## Где смотреть план/этапы
- `PROJECT_STEPS.md` — живой роадмап, какие фазы DONE и что дальше.

## Деплой (VPS + Dokploy) — текущий прод

- **Окружение**: бот запущен в Docker на VPS через Dokploy (Deploy from Git, образ из репо).
- **Данные**: host-path volume `/opt/calendar-data` на сервере → `/app/data` в контейнере.
- **Файлы в volume**: `client_secrets.json`, `token.json`, `smart_scheduler.db` лежат в `/opt/calendar-data` на VPS (копировать через `scp` или положить при первом запуске).
- **Env**: см. `.env.example`; пути — `DB_PATH=/app/data/smart_scheduler.db`, `GOOGLE_OAUTH_*_PATH=/app/data/...`.
- **Режим**: polling, один экземпляр, без внешнего реестра образов.
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

