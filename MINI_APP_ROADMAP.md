# Roadmap: Mini App + бот (техническое задание)

Документ описывает **нового бота в этом репо**: развёртывание через Dokploy; запись возможна и в чате бота, и через пользовательский Mini App; «Мои заявки» — в боте и в Mini App; админка целиком в отдельном админском Mini App. Бот в чате: запись (флоу сохранён), «Мои заявки», уведомления, модерация (confirm/reject/ban).

## Принятые решения (ТЗ)

| Вопрос | Решение |
|--------|---------|
| Запись на встречу | И в боте (чат), и в Mini App — оба канала |
| «Мои заявки» | И в боте (/my), и в пользовательском Mini App |
| Админка (timezone, work_schedule, blacklist, broadcast, pending list) | Только в отдельном **админском Mini App** (доступ по `user_id == ADMIN_ID`) |
| Домен | **calendar.vpncfo.ru** (CORS, BotFather, прокси) |
| Фронт Mini App | **React** (простой стек, сборка в Docker multi-stage) |

## Цель

- **Бот на VPS (Dokploy)**: polling; запись в чате (текущий FSM); кнопка «Открыть приложение» → пользовательский Mini App; «Мои заявки» (/my) в чате; уведомления (админу о новой заявке, пользователю о confirm/reject). Админки и модерации в чате нет — только в админском Mini App.
- **Пользовательский Mini App** (calendar.vpncfo.ru): запись (длительность → дата → время → анкета → pending), «Мои заявки».
- **Админский Mini App** (calendar.vpncfo.ru/admin или отдельный URL): настройки (timezone, work_schedule, blacklist), broadcast, список pending и действия. Доступ только для `ADMIN_ID` (проверка по initData на API).
- **Общая логика**: те же правила слотов, БД, уведомления через бота; API переиспользует код из репо.

## Архитектура (целевая)

```
[Telegram] —> бот (Dokploy): /start, /book (чат), /my (чат), кнопка "Приложение" → Mini App; уведомления (модерация только в админском Mini App)
     |
     +—> Пользовательский Mini App (https://calendar.vpncfo.ru) — запись, мои заявки
     +—> Админский Mini App (https://calendar.vpncfo.ru/admin) — вся админка (только ADMIN_ID)
                |
                v
         Backend API (тот же контейнер): FastAPI — слоты, booking, мои заявки; админ-эндпоинты (проверка ADMIN_ID по initData)
                |
                v
         БД SQLite + Google Calendar
```

- **Один контейнер**: бот (polling) + FastAPI (uvicorn) + статика двух Mini App (React build: `/` — клиент, `/admin` — админ). Volume `/app/data` для БД и OAuth.
- **Домен**: calendar.vpncfo.ru; в BotFather указываем URL пользовательского Mini App (и при необходимости отдельный URL для админского или путь `/admin`).
- Mini App передают `initData` в заголовке; API проверяет подпись и `user_id`; для админ-эндпоинтов дополнительно проверяется `user_id == ADMIN_ID`.

## Этапы (пошагово)

### 1. Backend API (контракт для Mini App)

- **Сделать**:
  - HTTP API (например FastAPI) на том же VPS или в том же приложении.
  - Эндпоинты (все требуют валидный `initData` в заголовке):
    - **Пользовательские**: `GET /slots/week`, `GET /slots/day?date=YYYY-MM-DD`, `POST /booking` (duration, date, time, name, subject, description?, email → meeting_id), `GET /my/meetings` (список заявок пользователя), `POST /my/meetings/{id}/cancel` (отмена pending).
    - **Админские** (доп. проверка `user_id == ADMIN_ID`): `GET /admin/settings` (timezone, work_schedule, buffer, blacklist), `PUT /admin/settings/...` (обновление настроек), `GET /admin/pending` (список pending с пагинацией), `POST /admin/meetings/{id}/confirm`, `POST /admin/meetings/{id}/reject`, `POST /admin/meetings/{id}/ban`, `POST /admin/broadcast` (дата + текст). Контракт уточняется при реализации.
  - Валидация: проверять `initData` (hash + данные), извлекать `user_id`; для админ-эндпоинтов — проверка на `ADMIN_ID`.
- **БД и время**: переиспользовать существующую логику (UTC в БД, таймзона из settings), те же функции: freebusy, work_schedule, buffer, blacklist, `create_meeting` — вызывать из FastAPI (общий код в этом репо).
- **initData**: проверка по [документации Telegram](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app): данные в query string, секрет = HMAC-SHA256(`bot_token`, "WebAppData"), сравнить с `hash` из initData.

### 2. Mini App frontend (React)

- **Стек**: React (Vite или CRA), сборка в Docker multi-stage (Node для build → статика в образ с FastAPI). Два приложения: пользовательское (корень/путь `/`) и админское (путь `/admin`) — можно два React-проекта в репо или один с роутингом по пути.
- **Пользовательский Mini App**:
  - Экран записи: длительность → неделя/дата → время → форма (имя, тема, описание, email) → отправка.
  - Экран «Мои заявки»: список pending/confirmed, отмена pending, кнопка «Новая заявка» (по желанию — шаблон из последней).
  - Все запросы к API с заголовком `X-Telegram-Init-Data` (initData от Telegram).
- **Админский Mini App**:
  - Настройки: timezone, work_schedule по дням, buffer, blacklist дат (CRUD).
  - Broadcast по дате.
  - Список pending с пагинацией и модерация (confirm/reject/ban) — полный функционал в Mini App, админ может не пользоваться чатом бота.
- **Общее**: `Telegram.WebApp.ready()`, при необходимости `expand()`; домен — https://calendar.vpncfo.ru. **Дизайн** — см. раздел «Дизайн Mini App» ниже.

### Дизайн Mini App (Design Spec)

**Style:** Apple-like / iOS system UI

**Goal:** Clean, modern, premium-looking Telegram Mini App UI in the style of native Apple iOS system apps (Settings, Calendar, Reminders). Calm, confident, utilitarian — not decorative or marketing-oriented.

**General principles:**
- Mobile-first, optimized for Telegram Mini App
- System-like appearance, Apple-inspired
- Minimalist, modern, premium
- One primary action per screen
- Clear visual hierarchy
- Calm and restrained, no visual noise

**Visual style:**
- Use Telegram theme variables for colors
- Light, airy background
- Soft surfaces with subtle elevation
- Rounded corners (12–16px)
- No gradients, no heavy shadows, no card-based layout, no decorative elements

**Color usage:**
- Background: `var(--tg-theme-bg-color)`
- Primary text: `var(--tg-theme-text-color)`
- Secondary text: `var(--tg-theme-hint-color)`
- Primary action: `var(--tg-theme-button-color)`
- Destructive action: iOS system red `#ff3b30`

**Typography:**
- System font stack (iOS-like)
- Headings: semibold; body: regular
- Large title: 20–22px; section title: 16–17px; body: 14–15px; caption: 12–13px
- Short, concise text only

**Layout:**
- Single-column layout
- Grouped sections similar to iOS Settings
- Soft background separation between groups
- Dense but readable spacing; no cards — use grouped surfaces

**User flow — создание заявки на встречу:**
- Large title: «Запрос встречи»
- Grouped form: date picker, time picker, optional comment
- Inputs like iOS system fields: soft background, no visible borders
- One primary full-width button at bottom, rounded ~14px: «Отправить»

**Admin flow — список заявок:**
- List styled like iOS List
- Item: primary text = user name, secondary = date and time
- No avatars; clear tap feedback

**Admin flow — детали заявки:**
- iOS-style bottom sheet, rounded top corners, soft slide-up
- Content: user name, date/time, optional comment
- Actions: primary «Подтвердить»; destructive text «Отклонить»

**Animations:** Subtle and fast (200–250ms), fade + slight translate; no bounce or playful motion.

**Icons:** Avoid if possible; if used: simple, SF Symbols–like, monochrome.

**States:** Loading = subtle spinner; disabled = reduced opacity; errors = short text + red accent, no modal dialogs.

**Explicitly avoid:** Material Design; Telegram bot–style UI; marketing/landing visuals; cards with shadows; bright/saturated colors; excessive text.

**Overall feel:** Calm, modern, Apple-like system interface — native, trustworthy, focused on fast task completion.

### 3. Интеграция бота и Mini App

- **В боте**:
  - `/start`: главное меню — «Записаться» (флоу в чате), «Мои заявки» (/my), кнопка «Открыть приложение» → `BOT_WEBAPP_URL` (https://calendar.vpncfo.ru). В BotFather прописать URL пользовательского Mini App (Menu Button / Mini App).
  - Запись в чате сохраняется (/book, текущий FSM). Модерация только в админском Mini App; в чат админу — только уведомление «Новая заявка» (без кнопок).
- **После создания заявки** (из чата или из Mini App): админ видит заявку в админском Mini App и модерирует там; в чат бота админу можно слать только уведомление «Новая заявка» (без кнопок). Пользователю в Mini App — «Заявка отправлена».

### 4. Безопасность и окружение

- **initData**: всегда проверять на бэкенде (подпись от Telegram), извлекать `user_id`. Для админ-эндпоинтов проверять `user_id == ADMIN_ID`.
- **HTTPS**: TLS на стороне Dokploy/прокси; приложение слушает HTTP внутри.
- **CORS**: разрешить origin `https://calendar.vpncfo.ru` (и при необходимости `https://web.telegram.org` для Web A/B).
- **Env**: `BOT_WEBAPP_URL=https://calendar.vpncfo.ru`, `ADMIN_ID` уже есть; при двух приложениях один домен — путь `/admin` для админского Mini App.

### 5. Деплой (Dokploy)

- **Один сервис**: один контейнер = бот (polling) + FastAPI (uvicorn) + статика Mini App. CMD запускает обе задачи (например скрипт, поднимающий бота в asyncio-таске и uvicorn на 0.0.0.0:8000).
- **Порты**: пробросить один (8000) для HTTP; TLS на стороне Dokploy/прокси. Бот наружу не светит.
- **Volume**: host-path → `/app/data` (БД, OAuth-файлы), как в текущем деплое.
- **Env**: текущие переменные + `BOT_WEBAPP_URL=https://calendar.vpncfo.ru` (кнопка в боте и CORS; при одном домене CORS origin = этот же URL).

## Проверка технологий (подходят для Dokploy)

| Компонент | Выбор | Примечание |
|-----------|--------|------------|
| Язык/рантайм | Python 3.11 | Уже в Dockerfile, Dokploy поддерживает |
| Бот | aiogram 3.x | Polling, без входящего HTTP — ок |
| API | FastAPI + uvicorn | Добавить в requirements; асинхронно, общая asyncio с ботом при одном процессе |
| БД | SQLite | Один контейнер = один процесс записи; при двух сервисах — общий volume, WAL |
| Google Calendar | Текущая интеграция | Без изменений, пути из env |
| Frontend Mini App | React | Два приложения (пользовательское + админское); сборка multi-stage в Dockerfile (Node для build), раздача через FastAPI StaticFiles |
| Валидация initData | HMAC-SHA256 (Telegram) | Библиотека или свой код на `cryptography`/стандартный `hmac`; добавить в зависимости при необходимости |
| HTTPS | На стороне прокси | Dokploy даёт домен и TLS; приложение отдаёт HTTP внутри |

Зависимости к добавлению: `fastapi`, `uvicorn[standard]`; для проверки initData — стандартный `hmac` достаточен (секрет = SHA256 от `BOT_TOKEN`).

## Что переиспользовать из текущего проекта (концептуально)

- Правила слотов: freebusy, work_schedule по дням, buffer_hours, blacklist_dates.
- Структура заявки: user_id, start_time (UTC), duration, name, subject, description, email, status=pending.
- Уведомления: тексты из `meeting_formatter`; уведомления админу/пользователю в чат бота по желанию сохраняем (при модерации из админского Mini App можно дополнительно слать сообщения в чат).
- Модерация: логика confirm/reject/ban в API для админского Mini App; в боте только уведомления (без inline-кнопок модерации).

## Реализация в этом репо

- **Один репо**: бот (чат: /book, /my, кнопка в Mini App) + FastAPI (пользовательские и админские эндпоинты) + два React-приложения (пользовательское и админское), статика с одного домена calendar.vpncfo.ru.
- **Бот**: сохраняем FSM записи в чате и «Мои заявки» (/my). Убираем из бота только админ-панель (/admin) — вся админка в админском Mini App. Модерация доступна в админском Mini App; уведомления в чат при новых заявках/решениях — на выбор (можно оставить).
- **API и логика**: переиспользовать `database/`, `services/google_api.py`, логику слотов и модерации из `handlers/booking.py` и `handlers/moderation.py`.

---

*Документ обновлён 2026-02-07. ТЗ: запись и «Мои заявки» — бот + Mini App; админка — только админский Mini App; домен calendar.vpncfo.ru; фронт React. Деплой Dokploy.*
