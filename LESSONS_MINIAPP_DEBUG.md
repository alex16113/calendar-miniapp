# Уроки отладки Telegram Mini App (2026-02-07)

Документ описывает все проблемы, с которыми столкнулись при деплое Mini App на Dokploy, и их решения.

---

## Проблема 1: Белый экран в Telegram (инициализация SDK)

### Симптом
- В обычном браузере (https://calendar.vpncfo.ru) — всё работает
- В Telegram WebView — белый экран, ничего не загружается
- Логи Dokploy показывают 304/200 — файлы отдаются

### Диагностика
Web Inspector в Telegram показал, что файлы загружаются, но React не рендерится.

### Причина
`Telegram.WebApp.ready()` и `expand()` вызывались в React `useEffect` — **после первого рендера**. Telegram WebView требует инициализацию SDK **до** загрузки приложения.

### Решение
Переместили инициализацию в `mini-app/index.html` в синхронный скрипт перед загрузкой React:

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

Убрали `useEffect` из `App.tsx`.

### Урок
**Telegram SDK инициализируется максимально рано** — в `<head>` или начале `<body>`, до любых фреймворков (React/Vue/Angular). Вызов в `useEffect` — слишком поздно.

---

## Проблема 2: React Router — "No routes matched location"

### Симптом
- Приложение загружается
- В консоли: `No routes matched location`
- React не рендерит ничего (пустой `<div id="root">`)
- В Elements видно только `<div id="root"></div>`

### Причина
Telegram может добавлять служебные параметры к URL:
- `#/tgWebAppVersion=7.10`
- `#/tgWebAppPlatform=ios`
- Или другие query параметры

React Router не находит роут для этих путей → ошибка → белый экран.

### Решение
Добавили fallback route в `App.tsx`:

```tsx
<Routes>
  <Route path="/" element={<Home />} />
  <Route path="/book" element={<Booking />} />
  <Route path="/my" element={<MyMeetings />} />
  <Route path="/admin" element={<Admin />} />
  {/* Fallback: любой неизвестный путь → главная */}
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes>
```

### Урок
**Всегда добавляй fallback route** (`path="*"`) в SPA — обрабатывает неожиданные пути, 404, служебные параметры и т.д.

---

## Проблема 3: 401/422 ошибки — валидация initData не проходила

### Симптом
- Приложение открывается
- initData передаётся (681 символ)
- Все API запросы возвращают 401 "Invalid or expired init data"
- В консоли: `[API] Request failed: 401`

### Диагностика
Логи Dokploy с `LOG_LEVEL=DEBUG` показали:
```
DEBUG | Parsed params keys: ['user', 'chat_instance', 'chat_type', 'auth_date', 'signature']
WARNING | HMAC mismatch! computed=abc..., received=def...
```

Заметили: Telegram передаёт **`signature`** вместо **`hash`**.

### Причина (глубинная)

**Telegram Bot API 8.0+ (ноябрь 2024) ввёл новый формат валидации Mini Apps.**

Теперь существуют **ДВА формата валидации initData**:

#### Формат 1: HMAC-SHA256 (старый, до Bot API 8.0)

**Поле:** `hash`

**Алгоритм:**
1. Исключить `hash` из параметров (оставить всё остальное, включая `signature` если есть)
2. Отсортировать параметры по ключу: `key=value\nkey=value\n...`
3. Вычислить секретный ключ:
   ```python
   secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
   ```
4. Вычислить подпись:
   ```python
   computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
   ```
5. Сравнить `computed_hash` с `hash` из initData

**Важно:** `signature` (если есть) **ОСТАЁТСЯ** в data_check_string при HMAC валидации!

#### Формат 2: Ed25519 (новый, Bot API 8.0+)

**Поле:** `signature` (base64url-encoded)

**Алгоритм:**
1. Исключить `hash` **И** `signature` из параметров
2. Отсортировать параметры: `key=value\nkey=value\n...`
3. Извлечь `bot_id` из `bot_token` (часть до двоеточия: `"123456:ABCdef"` → `"123456"`)
4. Построить строку для верификации:
   ```python
   verify_string = f"{bot_id}:WebAppData\n{data_check_string}"
   ```
5. Декодировать `signature` из base64url (добавить padding если нужно)
6. Верифицировать Ed25519 подпись:
   ```python
   Ed25519_Verify(
       public_key=TELEGRAM_PUBLIC_KEY,  # константа от Telegram
       signature=decoded_signature,
       message=verify_string
   )
   ```

**Публичный ключ Telegram (production):**
```
e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d
```

**Публичный ключ Telegram (test):**
```
40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec
```

### Почему новый формат?

**Безопасность:** Ed25519 позволяет **третьим сторонам** валидировать initData без знания секретного токена бота. Для валидации нужен только:
- Публичный ключ Telegram (константа)
- bot_id (не секрет, виден всем)

Это полезно для:
- Analytics провайдеров
- Third-party сервисов
- CDN с проверкой на edge

### Решение

Реализовали **оба метода** валидации:

```python
# Пробуем HMAC (если есть hash)
if received_hash:
    hmac_params = {k: v for k, v in params.items() if k != "hash"}
    hmac_dcs = "\n".join(f"{k}={v}" for k, v in sorted(hmac_params.items()))
    valid = _validate_via_hmac(hmac_dcs, bot_token, received_hash)

# Пробуем Ed25519 (если есть signature и HMAC не сработал)
if not valid and received_signature:
    ed_params = {k: v for k, v in params.items() if k not in ("hash", "signature")}
    ed_dcs = "\n".join(f"{k}={v}" for k, v in sorted(ed_params.items()))
    valid = _validate_via_ed25519(ed_dcs, bot_token, received_signature)
```

Добавили зависимость `cryptography>=43.0.0` для Ed25519.

### Урок

**Ключевые моменты:**

1. **Telegram может передавать ОБА поля** (`hash` и `signature`) в переходный период
2. **При HMAC** валидации: `signature` **ОСТАЁТСЯ** в data_check_string
3. **При Ed25519** валидации: оба поля **ИСКЛЮЧАЮТСЯ** из data_check_string
4. **Ed25519** добавляет префикс `{bot_id}:WebAppData\n` к строке для верификации
5. **Порядок параметров в HMAC критичен:**
   - ✅ `hmac.new(key=b"WebAppData", msg=bot_token, ...)`
   - ❌ `hmac.new(key=bot_token, msg=b"WebAppData", ...)` — НЕПРАВИЛЬНО!

**Документация:**
- Старый формат: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
- Новый формат: https://docs.telegram-mini-apps.com/platform/init-data#using-telegram-public-key

---

## Проблема 4: API параметр date_str vs date

### Симптом
- Недели загружаются (дни с галочками видны)
- При клике на день → 422 ошибка
- Консоль: `Field required: date_str`

### Причина
Несоответствие названий:
- Клиент (`mini-app/src/api.ts`): `getSlotsDay(date: string, ...)`
- API (`api/app.py`): `async def slots_day(..., date_str: str = Query(...))`

FastAPI ожидал `date_str`, клиент отправлял `date`.

### Решение
Изменили параметр в API с `date_str` на `date`:

```python
@app.get("/slots/day")
async def slots_day(
    user_id: int = Depends(get_telegram_user_id),
    date: str = Query(..., description="Дата YYYY-MM-DD"),  # ← было date_str
    duration: int = Query(30, description="Длительность в минутах"),
):
    slots = await get_day_slots(date_str=date, duration_minutes=duration)  # внутри всё равно date_str
    return {"date": date, "slots": slots}
```

### Урок
**API контракт должен совпадать с клиентом.** Используй единый источник истины (OpenAPI spec / TypeScript types) или проверяй вручную.

---

## Итоговые файлы, которые менялись

### Изменено:
- `mini-app/index.html` — инициализация Telegram SDK
- `mini-app/src/App.tsx` — fallback route, убрали useEffect
- `mini-app/src/main.tsx` — ErrorBoundary, детальное логирование
- `mini-app/src/pages/Home.tsx` — сообщение если initData отсутствует
- `mini-app/src/api.ts` — клиентское логирование для диагностики
- `api/app.py` — переименование параметра `date_str` → `date`, расширенный CORS
- `api/telegram_webapp.py` — полная переработка с поддержкой HMAC и Ed25519
- `api/deps.py` — детальное логирование валидации
- `requirements.txt` — добавлен `cryptography>=43.0.0`
- `.env.example` — добавлены опции для отладки

### Создано:
- `mini-app/src/ErrorBoundary.tsx` — компонент для отлова ошибок React
- `TROUBLESHOOT_MINIAPP.md` — общая диагностика
- `DEBUG_422_ERRORS.md` — диагностика ошибок валидации
- `DEBUG_TELEGRAM_WEBVIEW.md` — диагностика загрузки в WebView
- `FIX_BOTFATHER.md` — настройка Menu Button
- `FIX_401_ERRORS.md` — исправление ошибок авторизации
- `QUICK_FIX.md` — временное отключение валидации
- `CHECK_BOT_TOKEN.md` — проверка токена
- `LESSONS_MINIAPP_DEBUG.md` — этот файл

---

## Рекомендации на будущее

### 1. Инициализация Telegram SDK
- Всегда в `index.html`, синхронно, до загрузки фреймворка
- Проверяй наличие объекта перед вызовом: `if (window.Telegram?.WebApp)`

### 2. React Router в Mini Apps
- Используй `HashRouter` (не `BrowserRouter`) — не требует серверной настройки
- Всегда добавляй fallback route `<Route path="*">`
- Telegram может добавлять query параметры к URL

### 3. Валидация initData
- С Bot API 8.0+ (ноябрь 2024) — **два формата**: HMAC и Ed25519
- Проверяй оба формата последовательно
- При HMAC: исключай только `hash`, оставляй `signature`
- При Ed25519: исключай оба, добавляй префикс `{bot_id}:WebAppData\n`
- Используй библиотеку `cryptography` для Ed25519

### 4. Отладка Mini Apps
- **Telegram Desktop** — лучший инструмент: Cmd+Alt+I (Mac) / Ctrl+Shift+I (Windows)
- Добавляй детальное логирование на клиенте и сервере
- Визуальные индикаторы загрузки помогают понять где остановилось
- `LOG_LEVEL=DEBUG` в продакшене для диагностики (временно)

### 5. CORS для Mini Apps
- Обязательно: `https://web.telegram.org`
- Рекомендуется: regex для всех поддоменов `https://.*\.telegram\.org`
- Telegram WebView в iOS/Android может использовать разные origins

### 6. Menu Button vs Direct Link
- **Menu Button** (синяя кнопка внизу) — передаёт валидный initData
- **Прямая ссылка** в браузере — initData будет пустой
- Всегда тестируй через Menu Button, не через браузер

---

## Ссылки на документацию

- Telegram Bot API: https://core.telegram.org/bots/webapps
- Telegram Mini Apps (community): https://docs.telegram-mini-apps.com/platform/init-data
- Bot API Changelog: https://core.telegram.org/bots/api-changelog
- Bot API 8.0 (ноябрь 2024): https://telegram.org/blog/fullscreen-miniapps-and-more

---

## Инструменты для отладки

### Обязательные
- **Telegram Desktop** с DevTools (Cmd+Alt+I)
- **Web Inspector** для iOS (Safari → Develop)
- **Chrome Inspect** для Android (`chrome://inspect`)

### Полезные env для диагностики
- `LOG_LEVEL=DEBUG` — детальные логи сервера
- `DISABLE_INIT_DATA_CHECK=1` — временное отключение валидации (только для отладки!)
- `INIT_DATA_MAX_AGE_SECONDS=604800` — увеличенный TTL (7 дней)

### Визуальная диагностика
Добавили статус загрузки прямо в HTML:
```html
<script>
  window.addEventListener('DOMContentLoaded', function() {
    updateStatus('Проверка Telegram SDK...');
    // ... шаги загрузки
    updateStatus('initData length: ' + initData.length);
  });
</script>
```

---

*Документ создан 2026-02-07. Все проблемы решены, приложение работает с правильной валидацией initData.*
