# Changelog — 2026-02-07 (Деплой Mini App)

**Дата:** 2026-02-07  
**Автор:** Агент Claude Sonnet 4.5  
**Цель:** Деплой Mini App на Dokploy, отладка белого экрана и валидации initData

---

## Что было до начала дня

- ✅ Backend API полностью реализован (FastAPI, 8 эндпоинтов)
- ✅ Frontend Mini App (React + TypeScript + Vite)
- ✅ Multi-stage Dockerfile (Node → Python)
- ✅ Локально всё работает
- ❌ Не задеплоено на Dokploy

---

## Что сделано 2026-02-07

### 1. Деплой на Dokploy

#### Настройки Dokploy
- **Репозиторий:** https://github.com/alex16113/calendar-miniapp (ветка `main`)
- **Домен:** calendar.vpncfo.ru
- **HTTPS:** Let's Encrypt (автоматически)
- **Volume:** `/app/data` для БД и OAuth
- **Env:** `BOT_TOKEN`, `ADMIN_ID`, `BOT_WEBAPP_URL=https://calendar.vpncfo.ru`, Google OAuth настройки
- **Автодеплой:** при push в `main` → rebuild + restart

#### Menu Button в @BotFather
- Команда: `/setmenubutton`
- URL: `https://calendar.vpncfo.ru`
- Текст: "📅 Открыть приложение"

### 2. Отладка проблем

#### Проблема 1: Белый экран в Telegram (решена ✅)

**Симптом:**
- Через браузер (https://calendar.vpncfo.ru) — работает
- В Telegram WebView — белый экран
- Dokploy логи: 200/304, файлы отдаются

**Причина:**
`Telegram.WebApp.ready()` и `expand()` вызывались в React `useEffect` — слишком поздно для Telegram WebView.

**Решение:**
Переместили инициализацию в `mini-app/index.html` (синхронный скрипт до загрузки React):

```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script>
  (function() {
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }
  })();
</script>
```

**Изменённые файлы:**
- `mini-app/index.html` — добавлен синхронный скрипт
- `mini-app/src/App.tsx` — убран useEffect с инициализацией

#### Проблема 2: React Router "No routes matched location" (решена ✅)

**Симптом:**
- Приложение загружается
- В консоли: `No routes matched location`
- Белый экран (ничего не рендерится)

**Причина:**
Telegram может добавлять служебные параметры к URL (например, `#/tgWebAppVersion=7.10`). React Router не находит роут для этих путей.

**Решение:**
Добавили fallback route в `App.tsx`:

```tsx
<Route path="*" element={<Navigate to="/" replace />} />
```

**Изменённые файлы:**
- `mini-app/src/App.tsx` — добавлен fallback route

#### Проблема 3: 401 ошибки валидации initData (решена ✅, критическая)

**Симптом:**
- Приложение открывается
- initData передаётся (681 символ)
- Все API запросы → 401 "Invalid or expired init data"
- Логи: `HMAC mismatch!`

**Диагностика:**
```
DEBUG | Parsed params keys: ['user', 'chat_instance', 'chat_type', 'auth_date', 'signature']
WARNING | HMAC mismatch! computed=abc..., received=def...
```

Telegram передаёт **`signature`** вместо **`hash`**.

**Причина (глубинная):**

Telegram Bot API 8.0+ (ноябрь 2024) ввёл **новый формат валидации** — Ed25519 с полем `signature`.

**Два формата валидации:**

1. **HMAC-SHA256 (старый, до Bot API 8.0):**
   - Поле: `hash`
   - Алгоритм: `secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)`, затем `HMAC_SHA256(key=secret_key, msg=data_check_string)`
   - data_check_string: все параметры **кроме `hash`** (signature остаётся, если есть)

2. **Ed25519 (новый, Bot API 8.0+):**
   - Поле: `signature` (base64url)
   - Алгоритм: Ed25519 верификация с публичным ключом Telegram
   - data_check_string: все параметры **кроме `hash` И `signature`**
   - verify_string: `{bot_id}:WebAppData\n{data_check_string}`

**Ключевая находка:**
initData может содержать **оба поля** (`hash` и `signature`) одновременно!

**Решение:**

Полностью переписали `api/telegram_webapp.py`:

```python
def validate_init_data(data: str, bot_token: str, max_age_seconds: int = 86400) -> dict:
    params = parse_qs_to_dict(data)
    
    # Пробуем HMAC (если есть hash)
    received_hash = params.get("hash")
    if received_hash:
        hmac_params = {k: v for k, v in params.items() if k != "hash"}  # signature остаётся!
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(hmac_params.items()))
        if _validate_via_hmac(data_check_string, bot_token, received_hash):
            valid = True
    
    # Пробуем Ed25519 (если есть signature и HMAC не сработал)
    received_signature = params.get("signature")
    if not valid and received_signature:
        ed_params = {k: v for k, v in params.items() if k not in ("hash", "signature")}  # исключаем оба!
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(ed_params.items()))
        if _validate_via_ed25519(data_check_string, bot_token, received_signature):
            valid = True
    
    # Проверка auth_date TTL
    auth_date = int(params.get("auth_date", 0))
    age_seconds = time.time() - auth_date
    if age_seconds > max_age_seconds:
        raise ValueError(f"initData too old: {age_seconds}s > {max_age_seconds}s")
    
    return params
```

**Зависимости:**
Добавлен `cryptography>=43.0.0` для Ed25519.

**Изменённые файлы:**
- `api/telegram_webapp.py` — полностью переработан
- `api/deps.py` — детальное логирование валидации
- `requirements.txt` — добавлен `cryptography>=43.0.0`

**Документация:**
- https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app (старый формат)
- https://docs.telegram-mini-apps.com/platform/init-data (новый формат)

#### Проблема 4: 422 при выборе дня (решена ✅)

**Симптом:**
- Недели грузятся
- При клике на день → 422 ошибка "Field required: date_str"

**Причина:**
API ожидал параметр `date_str`, клиент отправлял `date`.

**Решение:**
Переименовали параметр в `api/app.py`:

```python
@app.get("/slots/day")
async def slots_day(
    user_id: int = Depends(get_telegram_user_id),
    date: str = Query(..., description="Дата YYYY-MM-DD"),  # было date_str
    duration: int = Query(30),
):
    slots = await get_day_slots(date_str=date, duration_minutes=duration)
    return {"date": date, "slots": slots}
```

**Изменённые файлы:**
- `api/app.py` — переименование параметра

### 3. Дополнительные улучшения

#### ErrorBoundary
Добавлен компонент для отлова ошибок React в production.

**Файлы:**
- `mini-app/src/ErrorBoundary.tsx` (создан)
- `mini-app/src/main.tsx` (обёрнут `<App />` в `<ErrorBoundary>`)

#### Детальное логирование

**Клиент:**
- `mini-app/index.html` — визуальные индикаторы загрузки (статус в HTML до React)
- `mini-app/src/api.ts` — `console.log` для initData и API запросов
- `mini-app/src/App.tsx` — логи routing
- `mini-app/src/main.tsx` — логи инициализации React

**Сервер:**
- `api/deps.py` — `logger.debug` для валидации (превью initData, результат)
- `api/telegram_webapp.py` — детальные логи HMAC/Ed25519 (parsed params, hashes, signature)

#### Расширенный CORS

Добавлен regex для всех Telegram origins:

```python
CORSMiddleware(
    allow_origins=[
        "https://calendar.vpncfo.ru",
        "https://web.telegram.org",
    ],
    allow_origin_regex=r"https://.*\.telegram\.org",  # поддержка iOS/Android WebView
    # ...
)
```

**Файлы:**
- `api/app.py` — добавлен `allow_origin_regex`

#### Сообщение об ошибке initData

Если initData пустой (открыто через браузер), показываем инструкцию:

```tsx
if (!initData || initData === "0") {
  return (
    <div>
      <h2>⚠️ Нет данных Telegram</h2>
      <p>Откройте через Menu Button в боте @google_calendar_booking1_bot</p>
    </div>
  );
}
```

**Файлы:**
- `mini-app/src/pages/Home.tsx` — проверка initData

#### Env для отладки

Добавлены опции в `.env.example`:

```env
# Временное отключение валидации (только для отладки!)
# DISABLE_INIT_DATA_CHECK=1

# Увеличенный TTL auth_date (7 дней вместо 1)
# INIT_DATA_MAX_AGE_SECONDS=604800
```

**Файлы:**
- `.env.example` — добавлены комментарии

### 4. Документация

Созданы гайды для будущего:

- **LESSONS_MINIAPP_DEBUG.md** — детальный разбор всех 4 проблем, объяснения форматов валидации
- **TROUBLESHOOT_MINIAPP.md** — общая диагностика (белый экран, 404, CORS)
- **DEBUG_TELEGRAM_WEBVIEW.md** — отладка загрузки в WebView
- **DEBUG_422_ERRORS.md** — диагностика ошибок валидации
- **FIX_BOTFATHER.md** — настройка Menu Button
- **FIX_401_ERRORS.md** — исправление ошибок авторизации
- **CHECK_BOT_TOKEN.md** — проверка токена
- **QUICK_FIX.md** — временное отключение валидации
- **NEXT_AGENT_PROMPT.md** — промпт для следующего агента (доработка дизайна)

Обновлены существующие:

- **PROJECT_STEPS.md** — добавлена секция "Сводка фактически внедрённых правок (2026-02-07)"
- **AGENT_HANDOFF.md** — добавлена секция "Изменения в процессе работы (2026-02-07, деплой и отладка)"
- **MINI_APP_ROADMAP.md** — обновлён статус (этапы 1-8 реализованы)
- **DEPLOY_DOKPLOY.md** — дополнен реальным опытом деплоя

---

## Итоговый статус

### ✅ Работает

- Mini App открывается в Telegram через Menu Button
- Валидация initData (HMAC + Ed25519)
- Загрузка недель с доступными днями
- Загрузка слотов времени на день
- Создание заявок (pending)
- Уведомления админу в чат с кнопками модерации
- Подтверждение заявки → событие в Google Calendar + Meet

### 🔧 TODO (следующая сессия)

1. Доработка дизайна форм (Apple-like по Design Spec)
2. Тестирование экрана "Мои заявки"
3. Тестирование админки в Mini App
4. Полировка UX (loading states, пустые состояния, анимации)
5. Опционально: убрать временные debug-логи

---

## Изменённые файлы

### Frontend (mini-app/)
- ✏️ `index.html` — инициализация Telegram SDK, визуальные индикаторы
- ✏️ `src/App.tsx` — fallback route, логи routing
- ✏️ `src/main.tsx` — ErrorBoundary, логи React
- ✏️ `src/api.ts` — логи initData и API
- ✏️ `src/pages/Home.tsx` — сообщение если initData пустой
- ➕ `src/ErrorBoundary.tsx` (создан)

### Backend (api/)
- ✏️ `app.py` — расширенный CORS, переименование параметра `date_str` → `date`
- ✏️ `telegram_webapp.py` — полная переработка (HMAC + Ed25519)
- ✏️ `deps.py` — детальное логирование валидации

### Конфиг
- ✏️ `requirements.txt` — добавлен `cryptography>=43.0.0`
- ✏️ `.env.example` — добавлены `DISABLE_INIT_DATA_CHECK`, `INIT_DATA_MAX_AGE_SECONDS`

### Документация
- ➕ `LESSONS_MINIAPP_DEBUG.md` (создан) — главный документ с разбором проблем
- ➕ `NEXT_AGENT_PROMPT.md` (создан) — промпт для следующей сессии
- ➕ `CHANGELOG_2026_02_07.md` (создан) — этот файл
- ➕ `TROUBLESHOOT_MINIAPP.md`, `DEBUG_*.md`, `FIX_*.md` (созданы) — гайды
- ✏️ `PROJECT_STEPS.md` — добавлена секция 2026-02-07
- ✏️ `AGENT_HANDOFF.md` — обновлён статус и изменения
- ✏️ `MINI_APP_ROADMAP.md` — обновлён статус

---

## Ключевые уроки

1. **Telegram SDK инициализируется рано:** в `<head>` или начале `<body>`, до фреймворков. `useEffect` — слишком поздно.

2. **Fallback route обязателен:** Telegram добавляет параметры к URL. Всегда добавляй `<Route path="*">`.

3. **Валидация initData в двух форматах:** Bot API 8.0+ использует Ed25519 (`signature`), но старый HMAC (`hash`) тоже может присутствовать. Проверяй оба.

4. **HMAC parameter order критичен:**
   - ✅ `hmac.new(key=b"WebAppData", msg=bot_token, ...)`
   - ❌ `hmac.new(key=bot_token, msg=b"WebAppData", ...)` — НЕПРАВИЛЬНО!

5. **data_check_string отличается:**
   - HMAC: исключаем только `hash` (signature остаётся)
   - Ed25519: исключаем оба (`hash` и `signature`)

6. **Детальное логирование спасает:** без `LOG_LEVEL=DEBUG` не нашли бы HMAC mismatch и `signature` в параметрах.

7. **Telegram Desktop — лучший инструмент для отладки:** Cmd+Alt+I (Mac) / Ctrl+Shift+I (Windows).

8. **Menu Button — единственный способ получить валидный initData:** прямая ссылка в браузере → initData пустой.

---

## Ссылки

- **Репо:** https://github.com/alex16113/calendar-miniapp
- **Домен:** https://calendar.vpncfo.ru
- **Бот:** @google_calendar_booking1_bot
- **Telegram Bot API 8.0:** https://telegram.org/blog/fullscreen-miniapps-and-more
- **Валидация (новая):** https://docs.telegram-mini-apps.com/platform/init-data
- **Валидация (старая):** https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

---

*Changelog создан 2026-02-07. Все проблемы решены, приложение работает.*
