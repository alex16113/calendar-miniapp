# Handoff для следующего агента (2026-02-07, обновлено)

Проект: **Calendar Mini App** — Telegram-бот + Mini App для записи на встречи. Деплой: Dokploy, домен calendar.vpncfo.ru.

## Где остановились

✅ **Этапы 1–8 реализованы и задеплоены на Dokploy**. Mini App работает в Telegram (calendar.vpncfo.ru). Отладка завершена — валидация initData (HMAC + Ed25519), загрузка слотов, создание заявок работают.

**Следующий шаг:** доработка дизайна и UX (по Design Spec из `MINI_APP_ROADMAP.md`), тестирование всех экранов (запись, "Мои заявки", админка).

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

### Этап 8 — Деплой (✅ ГОТОВО)
- **FastAPI**: раздача статики Mini App из `dist/` (StaticFiles, `html=True` для SPA fallback); CORS для `https://calendar.vpncfo.ru` и regex `https://.*\.telegram\.org` (поддержка всех Telegram origins); корень `/` отдаёт SPA (HashRouter).
- **Dockerfile**: multi-stage — Node 20 собирает `mini-app` в `dist/`, финальный образ Python 3.11 копирует только backend + `dist/`; один `CMD ["python", "run.py"]` (бот в фоне + uvicorn :8000); каталог `/app/data` для volume (БД, OAuth).
- **Dokploy**: задеплоено на calendar.vpncfo.ru, домен привязан, HTTPS через Let's Encrypt, volume `/app/data` примонтирован.
- **Отладка**: исправлены проблемы с инициализацией Telegram SDK, React Router, валидацией initData (HMAC + Ed25519). См. `LESSONS_MINIAPP_DEBUG.md`.
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

## Изменения в процессе работы (сессия 2026-02-07, до деплоя)

- **Сборка**: исправлен синтаксис в `mini-app/src/App.tsx` (`tw?.expand?.?.()` → `tw?.expand?.()`).
- **Venv**: путь в `.venv` заменён с `.../Calendar/.venv` на `.../Calendar miniapp/.venv` (pyvenv.cfg, activate, activate.csh, activate.fish); shebang в `bin/` из‑за пробела в пути использует симлинк без пробелов (см. выше).
- **Главная**: заголовок по центру «Запись. Календарь Алексея.»; текст «остальное подставится автоматически»; кнопки «Записаться» и «Открыть список» в одном стиле; блок «Админка» только при успешном GET /admin/settings.
- **Запись (Booking)**: полный флоу (длительность → неделя → день → время → форма → успех); подпись недели по `weekOffset` на клиенте («Неделя 3–9 фев»); «Следующая неделя» — ссылка `Link to={/book?w=${weekOffset+1}}` для надёжного клика в WebView; поддержка прямой ссылки `#/book?w=6`; текст «Нет свободных дней на эту неделю» без точки, по центру; при ошибках API (401/404) — пустой список без сырого JSON в UI.
- **Фон**: `body` и `#root` с `background: var(--tg-theme-bg-color)` (системная тема).
- **Админка**: добавлены все админ-эндпоинты и экран `/#/admin`; блок «Админка» на главной показывается только если пользователь — админ (проверка GET /admin/settings).

## Изменения в процессе работы (сессия 2026-02-07, деплой и отладка)

### Деплой на Dokploy (calendar.vpncfo.ru)

- **Репозиторий**: https://github.com/alex16113/calendar-miniapp (ветка `main`)
- **Dokploy**: создано приложение, подключен GitHub, настроен автодеплой
- **Домен**: calendar.vpncfo.ru привязан, HTTPS работает (Let's Encrypt)
- **Volume**: `/app/data` для БД и OAuth файлов
- **Env**: `BOT_TOKEN`, `ADMIN_ID`, `BOT_WEBAPP_URL=https://calendar.vpncfo.ru`, Google OAuth настройки
- **Menu Button**: настроен в @BotFather → `/setmenubutton` → URL: `https://calendar.vpncfo.ru`

### Отладка проблем (все решены ✅)

#### Проблема 1: Белый экран в Telegram
- **Симптом**: через браузер работает, в Telegram — белый экран
- **Причина**: `Telegram.WebApp.ready()` в React useEffect (слишком поздно)
- **Решение**: переместили инициализацию в `mini-app/index.html` (синхронный скрипт до React)
- **Файлы**: `mini-app/index.html`, `mini-app/src/App.tsx`

#### Проблема 2: React Router не находит роуты
- **Симптом**: загружается, но ничего не рендерится, `No routes matched location`
- **Причина**: Telegram добавляет служебные параметры к URL
- **Решение**: добавили fallback route `<Route path="*" element={<Navigate to="/" />} />`
- **Файлы**: `mini-app/src/App.tsx`

#### Проблема 3: 401 ошибки валидации initData (критическая)
- **Симптом**: все API запросы возвращают 401 "Invalid or expired init data"
- **Причина**: Telegram Bot API 8.0+ (ноябрь 2024) ввёл **новый формат валидации** — Ed25519 с полем `signature` вместо HMAC с полем `hash`
- **Ключевая находка**: initData может содержать **оба поля** (`hash` и `signature`) одновременно; при HMAC валидации `signature` **должна оставаться** в data_check_string (исключается только `hash`); при Ed25519 исключаются оба
- **Решение**: полностью переписали `api/telegram_webapp.py`:
  - Поддержка обоих форматов (HMAC и Ed25519)
  - Определение формата по наличию полей
  - Последовательная проверка обоих методов
  - Правильный порядок параметров: `hmac.new(key=b"WebAppData", msg=bot_token, ...)`
  - Ed25519 верификация через публичный ключ Telegram: `e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d`
- **Зависимости**: добавлен `cryptography>=43.0.0` для Ed25519
- **Файлы**: `api/telegram_webapp.py`, `api/deps.py`, `requirements.txt`
- **Документация**: https://docs.telegram-mini-apps.com/platform/init-data

#### Проблема 4: 422 при выборе дня
- **Симптом**: недели грузятся, при клике на день — 422 ошибка
- **Причина**: API ожидал параметр `date_str`, клиент отправлял `date`
- **Решение**: переименовали параметр в API с `date_str` на `date`
- **Файлы**: `api/app.py`

### Дополнительные улучшения

- **ErrorBoundary**: компонент для отлова ошибок React (`mini-app/src/ErrorBoundary.tsx`)
- **Детальное логирование**: клиент (`mini-app/src/api.ts`, `App.tsx`, `main.tsx`, `index.html`) и сервер (`api/deps.py`, `api/telegram_webapp.py`)
- **Визуальные индикаторы**: статус загрузки в HTML (до React), сообщение если initData пустой (`mini-app/src/pages/Home.tsx`)
- **CORS**: расширен regex `https://.*\.telegram\.org` для поддержки всех Telegram origins (iOS/Android WebView)
- **Env для отладки**: `LOG_LEVEL=DEBUG`, `DISABLE_INIT_DATA_CHECK=1` (временно), `INIT_DATA_MAX_AGE_SECONDS` (`.env.example`)

### Документация для будущего

- **LESSONS_MINIAPP_DEBUG.md** — детальный разбор всех 4 проблем с объяснениями
- **TROUBLESHOOT_MINIAPP.md** — общая диагностика проблем
- **DEBUG_*.md** — специфичные гайды по каждой проблеме
- **DEPLOY_DOKPLOY.md** — обновлён с учётом реального деплоя

### Текущий статус (2026-02-07, 12:00)

✅ **Всё работает:**
- Mini App открывается в Telegram через Menu Button
- Валидация initData (HMAC + Ed25519)
- Загрузка недель и дней с доступными слотами
- Выбор времени
- Создание заявок (pending)
- Уведомления админу в чат с кнопками модерации

🔧 **TODO (следующая сессия):**
- Доработка дизайна форм (Apple-like по Design Spec)
- Тестирование экрана "Мои заявки"
- Тестирование админки в Mini App
- Полировка UX
- Опционально: убрать временные debug-логи

## Установка через GitHub — что делать дальше

Код запушен в репозиторий: **https://github.com/alex16113/calendar-miniapp** (ветка `main`).

### 1. Деплой на Dokploy

1. **Создать приложение** в Dokploy: New Application → выбери тип (Docker / Docker Compose — в зависимости от того, как у тебя настроен Dokploy).
2. **Подключить GitHub**: источник образа — GitHub Repo. Укажи репо `alex16113/calendar-miniapp`, ветку `main`. Build: Dockerfile (корень репо).
3. **Порт**: в настройках сервиса укажи порт приложения **8000** (проброс наружу).
4. **Домен**: привяжи домен **calendar.vpncfo.ru** к этому сервису. HTTPS настраивается на стороне Dokploy/прокси.
5. **Volume**: добавь volume и примонтируй к пути контейнера **`/app/data`**. Сюда будут писаться БД и OAuth-файлы (см. env ниже).
6. **Переменные окружения** (из `.env.example`, значения подставить):
   - `BOT_TOKEN`, `ADMIN_ID` — обязательно.
   - `BOT_WEBAPP_URL=https://calendar.vpncfo.ru` — для кнопки в боте и CORS.
   - `DB_PATH=/app/data/smart_scheduler.db`
   - `GOOGLE_OAUTH_TOKEN_PATH=/app/data/token.json`, `GOOGLE_OAUTH_CLIENT_SECRETS_PATH=/app/data/client_secrets.json` (если OAuth).
   - Остальное: `CALENDAR_ID`, `TIMEZONE`, `WORK_START`, `WORK_END`, `BUFFER_HOURS`, `GOOGLE_AUTH_MODE=oauth` и т.д.
7. **Секреты** (credentials, token) не хранить в репо: положить на сервер в каталог, смонтированный в `/app/data`, или задать через env (если Dokploy поддерживает JSON в переменных — см. комментарии в `.env.example`).
8. Запустить деплой (Build & Deploy). После успешного билда контейнер будет слушать 8000 и раздавать API + Mini App с корня.

### 2. Локальный запуск из клона (без Dokploy)

```bash
git clone https://github.com/alex16113/calendar-miniapp.git
cd calendar-miniapp
docker build -t calendar-miniapp .
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" \
  -e BOT_TOKEN=... -e ADMIN_ID=... -e BOT_WEBAPP_URL=https://calendar.vpncfo.ru \
  -e DB_PATH=/app/data/smart_scheduler.db \
  -e GOOGLE_OAUTH_TOKEN_PATH=/app/data/token.json \
  -e GOOGLE_OAUTH_CLIENT_SECRETS_PATH=/app/data/client_secrets.json \
  -e CALENDAR_ID=... -e TIMEZONE=Europe/Moscow -e GOOGLE_AUTH_MODE=oauth \
  calendar-miniapp
```

Каталог `./data` на хосте должен содержать при необходимости `token.json`, `client_secrets.json`; БД создастся сама по `DB_PATH`.

### 3. Что проверить после деплоя на calendar.vpncfo.ru

1. **https://calendar.vpncfo.ru/health** → `{"status":"ok"}`.
2. **https://calendar.vpncfo.ru/** — открывается Mini App (главная).
3. В Telegram: кнопка «Открыть приложение» у бота ведёт на тот же домен; проверить слоты, запись, «Мои заявки», админку (под админ-аккаунтом).

### 4. Дальше (опционально)

- Экраны настроек и broadcast в UI админки (API уже есть).
- Доработка дизайна по Design Spec в `MINI_APP_ROADMAP.md`.

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
