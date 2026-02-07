# Диагностика 422 ошибок (initData validation)

## Проблема

Логи показывают:
```
INFO:     10.0.1.4:42820 - "GET /admin/settings HTTP/1.1" 422 Unprocessable Entity
INFO:     10.0.1.4:42820 - "GET /my/meetings?page=0&limit=10 HTTP/1.1" 422 Unprocessable Entity
INFO:     10.0.1.4:42820 - "GET /slots/week?week_offset=0&duration=15 HTTP/1.1" 422 Unprocessable Entity
```

**422 = Validation Error** — API не может обработать запрос, потому что либо:
- Telegram initData не передаётся в заголовке `X-Telegram-Init-Data`
- Или initData невалидный (неправильная подпись)

---

## Шаг 1: Проверь новые логи (после пересборки)

После пересборки в Dokploy (1-3 минуты) попробуй открыть Mini App снова.

### В Telegram Desktop (если есть доступ):

1. Открой Telegram Desktop
2. Нажми **Cmd+Alt+I** (Mac) или **Ctrl+Shift+I** (Windows)
3. Открой Console
4. Открой бота → "Открыть приложение"
5. Смотри в консоли строки:
   ```
   [API] Telegram object: exists / missing
   [API] WebApp object: exists / missing
   [API] initData length: 0 / 123
   ```

**Если `initData length: 0`** — Telegram SDK не инициализировался или initData пустой.

### В логах Dokploy:

Теперь должны быть строки типа:
```
WARNING | initData validation failed for data starting with: ...
```
или
```
DEBUG | initData is empty or whitespace
```

Пришли эти строки — станет ясно, в чём проблема.

---

## Шаг 2: Временно отключи валидацию (для диагностики)

Чтобы проверить, работает ли само приложение, временно отключи проверку initData.

**⚠️ ВАЖНО: это только для диагностики, НИКОГДА не оставляй это в проде!**

### В Dokploy:

1. Зайди в Applications → `calendar-miniapp` → **Environment Variables**
2. Добавь переменную:
   ```
   DISABLE_INIT_DATA_CHECK=1
   ```
3. Сохрани и перезапусти контейнер (Restart / Redeploy)

### Что это даёт:

- API будет возвращать данные БЕЗ проверки initData
- Все запросы будут выполняться от имени `ADMIN_ID`
- Ты увидишь, работает ли сам интерфейс

### Проверь:

1. Открой Mini App в Telegram
2. Теперь должна загрузиться главная страница (без белого экрана)
3. Попробуй открыть "Мои заявки" или "Записаться"

Если **ВСЁ РАБОТАЕТ** с `DISABLE_INIT_DATA_CHECK=1` — значит, проблема в initData.

---

## Шаг 3: Диагностика initData

Если с отключенной валидацией всё работает, нужно понять, почему initData не передаётся.

### Возможные причины:

#### 1. Скрипт Telegram SDK не загружается

**Проверка через браузер:**

1. Открой https://calendar.vpncfo.ru в обычном браузере
2. Открой DevTools (F12) → Console
3. Введи:
   ```javascript
   window.Telegram
   ```
4. Должен быть объект с `WebApp` внутри

Если `undefined` — скрипт SDK не загрузился.

**Решение:** Проверь, что в `index.html` есть:
```html
<script src="https://telegram.org/js/telegram-web-app.js"></script>
```

#### 2. Mini App открывается НЕ через Telegram

Если открываешь https://calendar.vpncfo.ru напрямую в браузере — initData будет пустой (это нормально).

**Решение:** Открывай ТОЛЬКО через Telegram → бот → кнопка "Открыть приложение".

#### 3. URL в BotFather неправильный

Если URL не указан или указан неправильно, Telegram не передаст initData.

**Проверка:**
1. @BotFather → /mybots → твой бот → Menu Button
2. URL должен быть: `https://calendar.vpncfo.ru`
3. БЕЗ `/#/` или `/index.html`

#### 4. Telegram не передаёт initData в мобильном WebView

В некоторых версиях Telegram (особенно старых) initData может быть пустым.

**Решение:**
- Обнови Telegram до последней версии
- Попробуй в Telegram Desktop (там точно работает)

---

## Шаг 4: После диагностики ВЫКЛЮЧИ dev-режим

Когда найдёшь проблему и исправишь:

1. В Dokploy → Environment Variables
2. **УДАЛИ** `DISABLE_INIT_DATA_CHECK` (или поставь `=0`)
3. Перезапусти контейнер

Иначе любой сможет использовать API без авторизации!

---

## Что делать дальше

1. **Сейчас**: дождись пересборки Dokploy (2-3 минуты)
2. **Попробуй открыть** Mini App в Telegram
3. **В Telegram Desktop**: открой консоль (Cmd+Alt+I) и посмотри логи `[API]`
4. **Пришли**:
   - Скриншот консоли (если есть доступ)
   - Логи Dokploy с новыми DEBUG/WARNING строками
   - Или попробуй временно включить `DISABLE_INIT_DATA_CHECK=1` и скажи, работает ли

С этой информацией найду точную причину проблемы.
