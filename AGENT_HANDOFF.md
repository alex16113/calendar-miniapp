# Handoff для следующего агента (2026-02-07)

Проект: **Calendar Mini App** — Telegram-бот + Mini App для записи на встречи. Деплой: Dokploy, домен calendar.vpncfo.ru.

## Где остановились

Реализованы **этапы 1–8** по `MINI_APP_ROADMAP.md`. **Деплой готов**: один образ (бот + uvicorn + статика Mini App). Дальше: задеплоить на Dokploy (calendar.vpncfo.ru), проверить в Telegram слоты, запись, «Мои заявки», админку.

## Что уже сделано

### Этап 1 — Backend API в одном процессе
- `api/app.py` — FastAPI, lifespan запускает бота в фоне.
- `run.py` — точка входа: `python run.py` поднимает uvicorn (порт 8000) и бота.
- `requirements.txt`: fastapi, uvicorn[standard].

### Этап 2 — Валидация initData
- `api/telegram_webapp.py` — проверка подписи Telegram WebApp initData (HMAC-SHA256), извлечение user_id.
- `api/deps.py` — зависимости `get_telegram_user_id`, `get_telegram_admin_id`.
- Тестовый эндпоинт `GET /me` возвращает user_id при валидном initData.

### Этап 3 — Слоты и бронирование
- `api/slots_service.py` — логика слотов (неделя, день, freebusy), переиспользует БД и Google API.
- `GET /slots/week`, `GET /slots/day`, `POST /booking` — работают; при создании заявки админу уходит уведомление в чат с кнопками модерации.

### Этап 4 — Доработка бота
- `config.py` — поле `bot_webapp_url` (из `BOT_WEBAPP_URL`).
- `.env.example` — пример `BOT_WEBAPP_URL`.
- `handlers/booking.py` — в главном меню кнопка «Открыть приложение» (WebApp).
- Админка в боте сохранена: /admin и кнопки модерации.

### Этап 5 — Мои заявки (API)
- `GET /my/meetings`, `POST /my/meetings/{meeting_id}/cancel`.
- Скрипт `scripts/gen_init_data.py USER_ID` — валидный initData для теста API без Telegram.

### Этап 6 — Пользовательский Mini App
- `mini-app/` — Vite + React + TypeScript, react-router-dom, HashRouter.
- Роуты: `/` — главная, `/#/book` — запись, `/#/my` — «Мои заявки», `/#/admin` — админка.
- **Полный флоу записи** на `/#/book`: длительность → неделя (с подписью «Неделя X–Y», переключение по `?w=0,1,2…`) → день → время → форма (имя, тема, описание, email) → POST /booking → экран успеха.
- Главная: заголовок по центру «Запись. Календарь Алексея.»; блоки «Новый запрос» и «Мои заявки» с кнопками; блок «Админка» показывается **только если** GET /admin/settings вернул 200 (т.е. открыл админ).
- Стили по Design Spec (Telegram theme vars, системный фон), прокси в dev на `/slots`, `/booking`, `/my`, `/admin`.

### Этап 7 — Админские эндпоинты и админский Mini App
- **API** (`api/admin.py`): GET/PUT `/admin/settings` (timezone, buffer_hours, work_schedule, blacklist), GET `/admin/pending`, POST `/admin/meetings/{id}/confirm|reject|ban`, POST `/admin/broadcast`. Все с `Depends(get_telegram_admin_id)`.
- **Админский экран** `/#/admin`: список pending с кнопками Подтвердить/Отклонить/В бан, пагинация; при 403 — «Доступ только для администратора».
- На главной блок «Админка» виден только админу (проверка через GET /admin/settings при загрузке).

### Этап 8 — Деплой
- **FastAPI**: раздача статики Mini App из `dist/` (StaticFiles, `html=True` для SPA fallback); CORS для `https://calendar.vpncfo.ru` и `https://web.telegram.org`; корень `/` отдаёт SPA (HashRouter — base URL не меняли).
- **Dockerfile**: multi-stage — Node 20 собирает `mini-app` в `dist/`, финальный образ Python 3.11 копирует только backend + `dist/`; один `CMD ["python", "run.py"]` (бот в фоне + uvicorn :8000); каталог `/app/data` для volume (БД, OAuth).
- Запуск образа: см. раздел «Запуск образа» ниже.

## Ключевые файлы

| Назначение | Файлы |
|------------|--------|
| Запуск бота + API | `run.py`, `api/app.py` |
| Конфиг | `config.py`, `.env` |
| API: слоты, бронирование, мои заявки | `api/app.py`, `api/slots_service.py`, `api/deps.py` |
| API: админка | `api/admin.py` |
| Валидация initData | `api/telegram_webapp.py` |
| Mini App | `mini-app/src/` — `App.tsx`, `api.ts`, `pages/Home.tsx`, `Booking.tsx`, `MyMeetings.tsx`, `Admin.tsx` |
| ТЗ и план | `MINI_APP_ROADMAP.md`, `HANDOFF.md` |

## Как запускать

- **Бот + API**: из корня репо `source .venv/bin/activate && python run.py` (порт 8000). Если путь с пробелом (например «Calendar miniapp»): симлинк `ln -sfn "$(pwd)/.venv" ~/Desktop/calendar-miniapp-venv` для работы shebang в `bin/`.
- **Mini App (dev)**: `cd mini-app && npm install && npm run dev` (порт 5173, прокси на 8000).
- **Тест API без Telegram**: `INIT_DATA=$(python scripts/gen_init_data.py TELEGRAM_USER_ID)` и `curl -H "X-Telegram-Init-Data: $INIT_DATA" http://localhost:8000/my/meetings`.

## Изменения в процессе работы (сессия 2026-02-07)

- **Сборка**: исправлен синтаксис в `mini-app/src/App.tsx` (`tw?.expand?.?.()` → `tw?.expand?.()`).
- **Venv**: путь в `.venv` заменён с `.../Calendar/.venv` на `.../Calendar miniapp/.venv` (pyvenv.cfg, activate, activate.csh, activate.fish); shebang в `bin/` из‑за пробела в пути использует симлинк без пробелов (см. выше).
- **Главная**: заголовок по центру «Запись. Календарь Алексея.»; текст «остальное подставится автоматически»; кнопки «Записаться» и «Открыть список» в одном стиле; блок «Админка» только при успешном GET /admin/settings.
- **Запись (Booking)**: полный флоу (длительность → неделя → день → время → форма → успех); подпись недели по `weekOffset` на клиенте («Неделя 3–9 фев»); «Следующая неделя» — ссылка `Link to={/book?w=${weekOffset+1}}` для надёжного клика в WebView; поддержка прямой ссылки `#/book?w=6`; текст «Нет свободных дней на эту неделю» без точки, по центру; при ошибках API (401/404) — пустой список без сырого JSON в UI.
- **Фон**: `body` и `#root` с `background: var(--tg-theme-bg-color)` (системная тема).
- **Админка**: добавлены все админ-эндпоинты и экран `/#/admin`; блок «Админка» на главной показывается только если пользователь — админ (проверка GET /admin/settings).

## Запуск образа (этап 8)

- Сборка: `docker build -t calendar-miniapp .`
- Запуск с volume для БД и OAuth:  
  `docker run -p 8000:8000 -v /path/on/host/data:/app/data -e BOT_TOKEN=... -e ADMIN_ID=... -e BOT_WEBAPP_URL=https://calendar.vpncfo.ru -e DB_PATH=/app/data/smart_scheduler.db -e GOOGLE_OAUTH_TOKEN_PATH=/app/data/token.json -e GOOGLE_OAUTH_CLIENT_SECRETS_PATH=/app/data/client_secrets.json ... остальные env ... calendar-miniapp`
- В Dokploy: домен calendar.vpncfo.ru, HTTPS на прокси; проброс порта 8000; volume на `/app/data`.

## Что проверить после деплоя на calendar.vpncfo.ru

1. `https://calendar.vpncfo.ru/health` → `{"status":"ok"}`.
2. `https://calendar.vpncfo.ru/` — открывается Mini App (главная).
3. Из Telegram: кнопка «Открыть приложение» → тот же домен; слоты, запись, «Мои заявки», админка (под админ-аккаунтом).

## Что сделать дальше

1. **Деплой на Dokploy**: создать сервис из образа, задать env и volume `/app/data`, привязать домен calendar.vpncfo.ru.
2. **Опционально**: экраны настроек и broadcast в UI админки (API уже есть); доработка дизайна по Design Spec.

## Документы

- **MINI_APP_ROADMAP.md** — полное ТЗ, архитектура, Design Spec, порядок разработки.
- **HANDOFF.md** — общее состояние бота, Google Calendar, как тестировать.

---

## Промпт для нового агента (скопируй в чат)

```
Проект: Calendar Mini App — Telegram-бот + Mini App для записи на встречи (календарь). Репозиторий с реализованными этапами 1–7.

Перед ответом прочитай правила из .cursor/rules. Отвечай на русском, кратко и по делу.

Контекст и текущее состояние — в файле AGENT_HANDOFF.md в корне репо. Там же список ключевых файлов, что сделано по этапам 1–7 и что изменяли в процессе работы.

Где остановились: этапы 1–7 готовы. Следующий шаг — этап 8 (деплой): один контейнер с ботом + FastAPI (uvicorn) + раздача статики Mini App (сборка из mini-app/ в dist/, отдача через FastAPI StaticFiles). Домен calendar.vpncfo.ru, HTTPS на стороне Dokploy/прокси.

Задачи:
1) Реализовать раздачу статики Mini App из FastAPI (см. MINI_APP_ROADMAP.md, этап 8): подключить StaticFiles для собранного mini-app/dist, при необходимости настроить base URL для SPA (HashRouter) и CORS для calendar.vpncfo.ru.
2) Подготовить/обновить Dockerfile: multi-stage (сборка фронта в Node, финальный образ с Python), один CMD запускает и бота, и uvicorn на порту 8000, volume для БД и OAuth-файлов.
3) Кратко отчитай: что сделал, как запускать образ, что проверить после деплоя на calendar.vpncfo.ru.

Полное ТЗ и порядок этапов — в MINI_APP_ROADMAP.md. Общий handoff бота и Google Calendar — в HANDOFF.md.
```
