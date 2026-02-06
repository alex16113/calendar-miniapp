---

## last_updated: 2026-02-06

project: Smart Scheduler

# Этапы реализации Smart Scheduler (бот → Mini App)

Формат работы: каждый завершённый этап отмечаем в этом файле + фиксируем ключевые решения/изменения (что поменяли/почему/как проверить).

## Логирование (сквозное требование)

- В коде используем `logging` (уже добавлено в `database/database.py` и `services/google_api.py`).
- В каждом этапе ниже есть **Test/Check** — это «как быстро убедиться, что не сломали».

---

## Сводка фактически внедрённых правок (2026-02-05)

Коротко, что именно было доделано/переделано поверх базового плана (с привязкой к файлам).

- **Google Calendar auth: OAuth 2.0 вместо Service Account (SaaS-ready)**:
  - **OAuth token lifecycle**: `services/google_calendar_service.py` (load/refresh/save `token.json`, auth URL)
  - **Переключаемый режим**: `GOOGLE_AUTH_MODE=oauth|service_account` в `config.py` + `.env.example`
  - **Calendar API wrapper**: `services/google_api.py` теперь поддерживает оба режима; `create_event(..., create_meet=True, attendee_email=...)`
  - **Первичная авторизация**: `scripts/google_oauth_init.py`
  - **Confirm UX**: `handlers/moderation.py` — пользователю отдаём только кнопку “📅 Открыть событие в календаре” (Meet создаётся внутри события при OAuth, но ссылку/кнопку в чат больше не показываем)
- **Модерация**:
  - **Reject с причиной**: `handlers/moderation.py` + `ModerationFSM` в `handlers/states.py`
  - **Confirm**: без лишней строки “это уведомление…” и без кнопки “добавить в календарь” (только открытие event)
- **Автоматизация**:
  - **TTL pending → expired**: `database/database.py:expire_old_pending_with_list`, фоновая задача в `bot.py`
  - env: `PENDING_TTL_HOURS`, `EXPIRE_CHECK_INTERVAL_SECONDS` (`config.py`, `.env.example`)
- **Админка `/admin` (редактируемая)**:
  - **Timezone**: кнопки городов РФ + “взять из Google Calendar” (`handlers/admin.py`, `services/google_api.py:get_calendar_timezone`)
  - **Work hours по дням недели**: `settings.work_schedule` (JSON) + UI выбора дня кнопками (`database/database.py`, `handlers/admin.py`, `handlers/booking.py`)
  - **Blacklist CRUD**: add/list/remove (`database/database.py`, `handlers/admin.py`)
  - **Broadcast**: рассылка confirmed по выбранной дате (`handlers/admin.py`, `database/database.py:list_meetings_in_time_range`)
- **UX оформления заявки (меньше мусора в чате)**:
  - **Подсказка имени из Telegram** + кнопки подтвердить/вручную: `handlers/booking.py`
  - **Очистка промежуточных сообщений** (best-effort delete): `handlers/booking.py` (`_ui_cleanup`, `_try_delete_user_message`)
- **Надёжность/улучшения (2026-02-05, после PHASE 7)**:
  - **Храним Google event данные в БД**: `meetings.google_event_id/google_event_html_link/google_meet_link` + мягкая миграция в `database/database.py` (`PRAGMA table_info` + `ALTER TABLE ... ADD COLUMN`)
  - **Confirm сохраняет event_id/link/meet в БД**: `handlers/moderation.py` + `database/database.py:set_meeting_google_event` (пользователю отдаём только `htmlLink`, Meet-линк храним, но не показываем)
  - **Анти-гонка слота**: повторный `freebusy` перед созданием `pending` (`handlers/booking.py`) и перед confirm (`handlers/moderation.py`)
  - **/admin pending list**: список pending с пагинацией и быстрыми действиями (`handlers/admin.py`, `database/database.py:list_pending_meetings/count_pending_meetings`)
  - **Единый formatter сообщений**: `services/meeting_formatter.py` (карточки админа/нотификации юзеру/expired)
  - **Структурные логи (request_id/user/chat/meeting)**:
    - контекст: `logging_context.py` (переменные `ctx_*`), `middlewares/log_context.py`
    - формат + автоподстановка через LogRecordFactory: `logging_setup.py`
    - подключение middleware: `bot.py`
    - Google create_event дополнительно логирует результат (event_id/наличие ссылок): `services/google_api.py`
  - **UX: Remember email + “Мои заявки”**:
    - **Подсказка email из прошлой заявки** (inline “использовать/ввести другой”): `handlers/booking.py` + `database/database.py:get_last_meeting_by_user`
    - **/my — список pending+confirmed + действия**: `handlers/my_requests.py` + `database/database.py:list_user_meetings/count_user_meetings`
    - **Отмена pending пользователем**: статус `cancelled` через `database/database.py:update_meeting_status_if_current` + уведомление админу
    - **Новая заявка по шаблону**: кнопка “Новая заявка (как прошлый раз)” → старт booking с прошлой длительностью и предзаполнением subject/description/email
    - **Кнопка “Мои заявки” в главном меню**: `handlers/booking.py:_main_menu_kb` + `handlers/common.py:/start` + обработчик текста в `handlers/my_requests.py`
  - **UX/стабильность админки и роутинга**:
    - `/admin` не должен “съедаться” FSM записи: порядок подключения роутеров `admin` перед `booking` в `bot.py`
    - исправлен callback `admin:pending` (падал из-за `state`): `handlers/admin.py`
    - после confirm/reject/ban админ получает «следующую pending» автоматически (если есть): `handlers/moderation.py`
    - `/start` и `/help` не показывают `/admin` не-админам: `handlers/common.py`
  - **Meet скрыт в сообщениях/кнопках**:
    - подтверждение пользователю больше не содержит строки `Meet: ...`: `services/meeting_formatter.py`
    - кнопка “🎥 Подключиться к Meet” убрана из confirm и из `/my`: `handlers/moderation.py`, `handlers/my_requests.py`

## Сводка фактически внедрённых правок (2026-02-06)

- **Деплой/секреты**:
  - добавлен скрипт `scripts/runtime_bootstrap.py` для записи JSON-секретов из env в файлы и проверки конфигурации
  - `.env.example` расширен примерами `GOOGLE_*_JSON`
  - `README.md` дополняет старт-команду для Railway и ограничения shared-хостинга

## Сводка фактически внедрённых правок (2026-02-06, деплой VPS + Dokploy)

- **Прод**: бот развёрнут на VPS через Dokploy (Deploy from Git, образ из репо).
- **Данные**: host-path `/opt/calendar-data` → `/app/data` в контейнере; `Dockerfile` и `.dockerignore` в корне.
- Документация обновлена: `HANDOFF.md`, `README.md`; план по Mini App вынесен в `MINI_APP_ROADMAP.md`.

---

## PHASE 0 — Подготовка репо и окружения

### 0.1. Python/виртуальное окружение

- **Deliverable**: скрипт `scripts/bootstrap.sh` создаёт venv `.venv` и ставит зависимости из `requirements.txt`.
- **Status**: READY (нужно один раз запустить локально).
- **Test/Check**:
  - `./scripts/bootstrap.sh`
  - `. .venv/bin/activate`
  - `python -V` (>=3.10)
  - `python -m pip show aiogram google-api-python-client pytz`

### 0.2. Конфиг и секреты

- **Deliverable**: `config.py` (env + `.env` без зависимостей) + пример `.env.example` + проверка `scripts/check_config.py`.
- **Status**: DONE
- **Security**: `credentials.json` остаётся локально в корне проекта, не коммитится.
- **Test/Check**:
  - `cp .env.example .env` и заполнить значения
  - `python scripts/check_config.py` (не выводит токен)

---

## PHASE 1 — База данных и настройки

### 1.1. Схема SQLite

- **Deliverable**: таблицы из ТЗ: `settings`, `meetings`, `blacklist_dates`, `users_blacklisted`.
- **Status**: DONE (см. `database/database.py:init_schema`).
- **Test/Check**: запуск `init_db()` создаёт файл `database/smart_scheduler.db` и таблицы.

### 1.2. Настройки в БД (timezone, working hours, buffer)

- **Deliverable**: API для чтения/записи настроек + дефолты (`Europe/Moscow`, рабочие интервалы, буфер).
- **Status**: DONE
- **Реализация**:
  - `Database.bootstrap_settings(...)` — заполняет дефолты, не перетирая существующие
  - `scripts/init_db.py` — инициализация БД и дефолтов из `.env`
- **Test/Check**:
  - `. .venv/bin/activate`
  - `python scripts/init_db.py`
  - повторный запуск `python scripts/init_db.py` должен показывать пустой `inserted_defaults={}`

---

## PHASE 2 — Каркас бота (aiogram 3.x)

### 2.1. Entry point + Dispatcher

- **Deliverable**: `bot.py` (или `main.py`) с запуском бота, регистрацией роутеров, инициализацией БД.
- **Logging**: лог старта, лог загрузки конфигурации (без токенов).
- **Test/Check**: бот стартует и отвечает на `/start`.
- **Status**: DONE
- **Реализация**:
  - `bot.py` — запуск, `init_db()`, `bootstrap_settings()`, polling
  - `handlers/common.py` — `/start`, `/help`

### 2.2. Базовые команды

- **Deliverable**: `/start`, `/help`, `/admin` (доступ по `ADMIN_ID`).
- **Test/Check**: `/admin` недоступна не-админу.
- **Status**: DONE
- **Реализация**:
  - `handlers/admin.py` — `/admin` + проверка `ADMIN_ID`

---

## PHASE 3 — FSM клиента (запись на встречу)

### 3.1. Выбор длительности

- **Deliverable**: кнопки 15/30/60/90, сохранение в FSM context.
- **Test/Check**: повторные нажатия не ломают состояние, есть кнопка «Назад» где нужно.
- **Status**: DONE (первый проход)
- **Реализация**:
  - `handlers/booking.py` — `/book`, кнопки длительности, сохранение в FSM
  - `handlers/states.py` — `BookingFSM`
  - `handlers/common.py` — кнопка “Записаться” на `/start`

### 3.2. Выбор даты (неделя + “следующая неделя”)

- **Deliverable**: календарный UI по неделям, отметка ✅ только там, где есть слоты.
- **Test/Check**: корректный переход между неделями.
- **Status**: DONE (без Google freebusy — только рабочие часы/буфер/blacklist)
- **Реализация**:
  - `handlers/booking.py` — неделя, “Следующая неделя”, “Назад”, выбор даты

### 3.3. Выбор времени (слоты шаг 30 мин)

- **Deliverable**: сетка слотов с учётом:
  - рабочего времени,
  - blacklist дат,
  - буфера безопасности,
  - занятости календаря (см. PHASE 5).
- **Test/Check**: слоты не показываются на blacklisted date, буфер реально режет доступные слоты.
- **Status**: DONE (без Google freebusy — только рабочие часы/буфер/blacklist)
- **Реализация**:
  - `handlers/booking.py` — слоты шаг 30 минут, кнопки “Назад/Отмена”, сохранение `time_local` в FSM

### 3.4. Анкета (имя/тема/описание/email)

- **Deliverable**: FSM шаги + валидация email + «Пропустить» для описания.
- **Test/Check**: некорректный email просит повторить, пропуск работает.
- **Status**: DONE
- **Реализация**:
  - `handlers/booking.py` — сбор `name/subject/description?/email`, skip description, `/cancel`
  - UX: предлагаем `Telegram full_name` кнопкой подтверждения + “ввести вручную”
  - UX: чистим промежуточные сообщения (best-effort), итоговое подтверждение остаётся

### 3.5. Создание pending-заявки

- **Deliverable**: запись в `meetings` со статусом `pending`, `created_at` UTC.
- **Test/Check**: запись появляется в БД, даты в UTC.
- **Status**: DONE
- **Реализация**:
  - `database/database.py:create_meeting(...)` — хранит `start_time/created_at` в UTC
  - `handlers/booking.py` — после email создаёт запись `meetings.status=pending` и отдаёт `meeting_id`

---

## PHASE 4 — Админ модерация

### 4.1. Уведомление админа о заявке + inline кнопки

- **Deliverable**: сообщение по шаблону ТЗ + кнопки `✅ Подтвердить / ❌ Отклонить / 🚫 В бан`.
- **Test/Check**: кнопки работают, повторное нажатие не приводит к двойным действиям (идемпотентность).
- **Status**: DONE
- **Реализация**:
  - `handlers/booking.py` — отправка админа алерта при создании `pending`
  - `handlers/moderation.py` — inline кнопки и обработчики callback

### 4.2. Confirm / Reject / Ban

- **Deliverable**:
  - confirm → статус `confirmed` + (см. PHASE 5) создание события в Google,
  - reject → статус `rejected` (с причиной),
  - ban → запись в `users_blacklisted` и дальнейшая блокировка действий пользователя.
- **Test/Check**: banned user не может записаться.
- **Status**: DONE (без Google event; создание события будет в PHASE 5.3)
- **Реализация**:
  - `handlers/moderation.py` — обновление статуса, бан пользователя, уведомление пользователя в чат
  - reject: запрос причины через FSM (`handlers/states.py:ModerationFSM`)

### 4.3. Список ожидания (pending)

- **Deliverable**: просмотр/поиск `pending` заявок из БД.
- **Test/Check**: выдача корректна, pagination/лимиты не ломают UI.

---

## PHASE 5 — Google Calendar API (Service Account)

### 5.1. Подключение (инициализация клиента)

- **КОД**: `services/google_api.py:build_calendar_service()` по умолчанию читает `credentials.json` из корня проекта.
- **Deliverable**: функция инициализации + единый объект service (или lazy init).
- **Test/Check**: локальная «смок-проверка» (одна команда/скрипт) делает запрос к Calendar API и получает ответ.
- **Status**: DONE
- **Реализация**:
  - `services/google_api.py:get_freebusy/create_event`
  - `scripts/check_google.py` — смок-проверка доступа к Calendar API

**Ответ на твой вопрос “на каком этапе подключение?”**

- **Первое подключение/проверка `credentials.json**`: именно **на PHASE 5.1**, сразу после того как есть каркас приложения и конфиг (PHASE 2), чтобы рано поймать проблемы с доступом.
- **Реальное использование в продуктовой логике**:
  - `freebusy` — в **PHASE 3.3** (построение слотов),
  - `create event` — в **PHASE 4.2** (кнопка confirm).

### 5.2. FreeBusy для вычисления доступных слотов

- **Deliverable**: запрос `freebusy` и вычитание занятых интервалов из рабочего времени.
- **Test/Check**: при создании события вручную в календаре слот исчезает из выдачи бота.
- **Status**: DONE (freebusy подключён в UI слотов; при ошибке — фолбэк на локальные слоты)
- **Реализация**:
  - `handlers/booking.py` — freebusy на неделю (для ✅) и на день (для слотов времени)

### 5.3. Создание события при confirm

- **Deliverable**:
  - `events.insert` (OAuth): `attendees` + `sendUpdates=all` + Google Meet (`conferenceDataVersion=1`)
  - `events.insert` (Service Account legacy): без attendees (ограничение без DWD)
  - UX: пользователю отправляем кнопку “📅 Открыть событие в календаре” (htmlLink)
- **Test/Check**:
  - в календаре владельца появляется event,
  - при OAuth: гостю уходит инвайт на email + Meet внутри события,
  - при legacy SA: инвайт не уходит (ожидаемо), но event открывается по ссылке.
- **Status**: DONE
- **Реализация**:
  - `handlers/moderation.py` — confirm создаёт event в Google, затем подтверждает заявку
  - `services/google_api.py:create_event` — insert (oauth/sa режим)

### 5.4. Миграция на OAuth 2.0 (Desktop App) — чтобы включить attendees + Google Meet

> Цель: уйти от Service Account (`credentials.json`) на OAuth 2.0 (`client_secrets.json` + `token.json`), чтобы бот действовал от имени владельца, мог слать инвайты (`attendees`) и создавать Meet.

#### 5.4.1. Конфиг и секреты

- **Deliverable**:
  - в корне проекта `client_secrets.json` / `client_secret.json` (Desktop OAuth Client ID) — не коммитить
  - в корне проекта `token.json` (создаётся после первого логина) — не коммитить
  - `.gitignore`: добавить `client_secrets.json`, `token.json`
  - `.env(.example)`:
    - `GOOGLE_OAUTH_CLIENT_SECRETS_PATH=client_secrets.json`
    - `GOOGLE_OAUTH_TOKEN_PATH=token.json`
    - (опционально для мягкой миграции) `GOOGLE_AUTH_MODE=oauth|service_account`
- **Status**: DONE
- **Test/Check**:
  - `python scripts/check_config.py` видит новые переменные, токены не печатает

#### 5.4.2. `GoogleCalendarService` (token load/refresh/save)

- **Deliverable**:
  - класс `GoogleCalendarService`, который:
    - грузит `token.json`, проверяет `creds.valid`
    - если протух — refresh через `refresh_token` и сохраняет `token.json`
    - если токена нет/refresh невозможен — печатает auth URL при старте (в терминал)
  - библиотеки: `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client`
  - логирование ключевых веток (load/refresh/need-auth)
- **Status**: DONE
- **Test/Check**:
  - удалить/переименовать `token.json` → старт бота/скрипта печатает URL
  - после авторизации `token.json` появляется
  - перезапуск без браузера работает (refresh/valid token)

#### 5.4.3. Скрипт первичной авторизации

- **Deliverable**: `scripts/google_oauth_init.py` создаёт `token.json` (без запуска бота).
- **Status**: DONE
- **Test/Check**: `python scripts/google_oauth_init.py` → появляется `token.json`

#### 5.4.4. Переключение freebusy/slots на OAuth

- **Deliverable**:
  - заменить текущую инициализацию Calendar service на OAuth-реализацию
  - сохранить фолбэк: при ошибке Google API UI слотов продолжает работать “локально”
- **Status**: DONE
- **Test/Check**:
  - freebusy реально влияет на ✅ в неделе и выдачу слотов (занятые интервалы исчезают)

#### 5.4.5. Confirm: attendees + Meet

- **Deliverable**:
  - `events.insert` с:
    - `attendees=[{"email": user_email}]`
    - `sendUpdates="all"`
    - `conferenceDataVersion=1` + `conferenceData.createRequest` (Meet)
  - (опционально) хранить `event_id` в БД для будущего cancel/update.
- **Status**: DONE
- **Test/Check**:
  - гостю уходит инвайт на email
  - в event есть Meet-ссылка

---

## PHASE 6 — Автоматизация и “непротухание”

### 6.1. TTL заявок (24 часа)

- **Deliverable**: периодическая задача: `expire_old_pending()` → `expired`.
- **Test/Check**: искусственно уменьшить TTL и убедиться, что pending становится expired.
- **Status**: DONE
- **Реализация**:
  - `database/database.py:expire_old_pending_with_list(...)`
  - `bot.py:_expire_pending_loop(...)` + env: `PENDING_TTL_HOURS`, `EXPIRE_CHECK_INTERVAL_SECONDS`

### 6.2. Буфер безопасности (например, 3 часа)

- **Deliverable**: запрет записи ближе чем N часов до старта (на этапе выдачи слотов).
- **Test/Check**: слоты “слишком близко” не показываются.
- **Status**: DONE
- **Реализация**:
  - `handlers/booking.py:_iter_slots(...)` использует `buffer_hours` из БД (настройка `BUFFER_HOURS`)

---

## PHASE 7 — Админ-настройки (/admin)

### 7.1. Таймзона

- **Deliverable**: хранение в `settings` + применение к отображению.
- **Test/Check**: одна и та же встреча отображается по-разному при смене timezone, при этом в БД UTC неизменен.
- **Status**: DONE
- **Реализация**:
  - `/admin` → “Таймзона” → кнопки городов РФ + “взять из Google Calendar” + fallback “другая…” (ручной ввод)
  - `handlers/admin.py`, `database/database.py:set_timezone`, `services/google_api.py:get_calendar_timezone`

### 7.2. Рабочие интервалы

- **Deliverable**: UI + хранение, влияние на выдачу слотов.
- **Test/Check**:
  - выставить Сб/Вс выходными → в эти дни слоты не показываются,
  - задать часы только для одного дня → слоты появляются только в этот день.
- **Status**: DONE
- **Реализация**:
  - хранение: `settings.work_schedule` (JSON по дням недели) (`database/database.py:get_work_schedule/set_work_schedule_day/get_work_hours_for_date`)
  - UI: `/admin` → “Рабочие часы” → выбор дня кнопками → “Задать часы” или “Выходной” (`handlers/admin.py`)
  - слоты: `handlers/booking.py:_iter_slots()` использует `get_work_hours_for_date(day)`

### 7.3. Blacklist дат

- **Deliverable**: включить/выключить конкретную дату, причина.
- **Test/Check**: дата исчезает из выдачи, запись невозможна.
- **Status**: DONE
- **Реализация**: `/admin` → “Blacklist дат” → список/добавить/удалить (`handlers/admin.py`, `database/database.py:add/remove/list_blacklist_dates`)

### 7.4. Broadcast

- **Deliverable**: рассылка по подтверждённым участникам на дату.
- **Test/Check**: получает только confirmed.
- **Status**: DONE
- **Реализация**:
  - `/admin` → `📣 Broadcast` → дата `YYYY-MM-DD` → текст → подтверждение.
  - получатели: `meetings.status=confirmed` с `start_time` в выбранных сутках (по таймзоне настроек).
  - `database/database.py:list_meetings_in_time_range(...)`

---

## PHASE 8 — “Полностью заработало” + подготовка к Mini App

### 8.1. Минимальный техдолг

- **Deliverable**: единый модуль конфигурации, нормальные ошибки, структурированные логи.
- **Test/Check**: быстрый прогон основных сценариев без ручных правок.

### 8.2. Контракты под Mini App (API-слой)

- **Deliverable**: выделить слой бизнес-логики так, чтобы UI был заменяем:
  - сейчас: Telegram chat UI,
  - потом: Telegram Mini App UI.
- **Идея**: добавить HTTP API (обычно `FastAPI`) для:
  - получения доступных слотов,
  - создания заявки,
  - статусов.
- **Test/Check**: API выдаёт те же слоты, что и бот.

---

## PHASE 9 — Telegram Mini App (WebApp)

### 9.1. Frontend mini app

- **Deliverable**: веб-интерфейс выбора длительности/даты/слота/анкеты внутри Telegram.
- **Test/Check**: работает `Telegram.WebApp`, корректная передача данных в backend.

### 9.2. Интеграция с ботом

- **Deliverable**: deep-link / кнопка “Открыть приложение” + подтверждения/нотификации остаются в боте.
- **Test/Check**: end-to-end: Mini App → заявка → админ confirm → event в календаре.

