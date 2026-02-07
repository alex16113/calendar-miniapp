# Исправление 401 "Invalid or expired init data"

## Проблема

Приложение открывается, но все API запросы возвращают **401 Unauthorized**.

initData передаётся (681 символ), но сервер отклоняет при валидации HMAC подписи или проверке времени.

---

## Быстрое решение: включи DEBUG логи

### В Dokploy:

1. Зайди в Applications → `calendar-miniapp` → **Environment Variables**
2. Найди переменную `LOG_LEVEL` или добавь новую:
   ```
   LOG_LEVEL=DEBUG
   ```
3. **Сохрани и перезапусти** контейнер (Restart)

### После перезапуска:

1. Открой Mini App в Telegram
2. Попробуй загрузить слоты
3. Зайди в **Dokploy → Logs**
4. Увидишь детальные логи:
   ```
   DEBUG | validate_init_data called, data length: 681
   DEBUG | Parsed params keys: ['auth_date', 'hash', 'query_id', 'user']
   DEBUG | Received hash: abc123...
   DEBUG | data_check_string preview: auth_date=1234...
   ```
5. **Найди строку с ошибкой:**
   - `WARNING | HMAC mismatch!` → проблема с подписью
   - `WARNING | initData auth_date too old` → проблема с TTL
   - `DEBUG | HMAC signature valid!` → подпись OK, ищи дальше

**Пришли сюда логи** — точно скажу в чём проблема.

---

## Возможные причины и решения

### 1. HMAC не совпадает (неправильный BOT_TOKEN)

**Симптом в логах:**
```
WARNING | HMAC mismatch! computed=abc123..., received=def456...
```

**Причина:** `BOT_TOKEN` в Dokploy не совпадает с реальным токеном бота.

**Решение:**
1. Открой @BotFather в Telegram
2. Отправь `/mybots` → выбери бота → **API Token**
3. Скопируй токен
4. В Dokploy → Environment Variables → `BOT_TOKEN` → вставь правильный токен
5. Перезапусти контейнер

### 2. auth_date слишком старый (TTL истёк)

**Симптом в логах:**
```
WARNING | initData auth_date too old: 90000s > 86400s
```

**Причина:** initData "протух" (старше 24 часов по умолчанию).

**Временное решение (для диагностики):**

В Dokploy → Environment Variables → добавь:
```
INIT_DATA_MAX_AGE_SECONDS=604800
```
(7 дней = 604800 секунд)

**Перезапусти** контейнер.

**Постоянное решение:**

Если auth_date действительно старый — нужно понять, почему Telegram передаёт старые данные. Обычно это не должно происходить.

### 3. initData повреждён при передаче

**Симптом в логах:**
```
DEBUG | No hash field in initData
```
или
```
DEBUG | initData parse_qsl failed
```

**Причина:** initData неправильно кодируется/декодируется в заголовке HTTP.

**Проверка:**

Смотри в Console (Web Inspector):
```
[API] initData length: 681
```

Если число меняется при каждом открытии — возможно, данные повреждаются.

**Решение:** Пока не требуется — этого не наблюдается в твоих логах.

---

## План действий (по порядку)

### ✅ Шаг 1: Включи DEBUG логи

```
LOG_LEVEL=DEBUG
```

Restart контейнера.

### ✅ Шаг 2: Открой Mini App и попробуй загрузить слоты

Telegram → бот → Menu Button → попробуй выбрать неделю.

### ✅ Шаг 3: Смотри логи в Dokploy

Dokploy → Logs → найди строки с `DEBUG` и `WARNING`.

### ✅ Шаг 4: Пришли логи сюда

Скопируй строки с:
- `validate_init_data called`
- `Parsed params keys`
- `HMAC mismatch` или `HMAC signature valid`
- `auth_date age`
- Любые WARNING или ERROR

### ✅ Шаг 5: Исправим проблему по логам

С детальными логами точно найдём причину.

---

## Если не хочется ждать — временный обход

Чтобы сразу проверить, что остальное работает:

В Dokploy → Environment Variables:
```
DISABLE_INIT_DATA_CHECK=1
```

Restart контейнера.

**⚠️ ВАЖНО:** Это отключает всю авторизацию! Используй ТОЛЬКО для проверки. Потом обязательно удали эту переменную.

С этой настройкой:
- Все запросы будут проходить
- user_id будет = ADMIN_ID
- Ты сможешь проверить слоты, запись, "Мои заявки" и т.д.

Если всё работает с отключенной валидацией — значит, проблема точно в HMAC или TTL.

---

## Итого: что делать СЕЙЧАС

1. **Dokploy → Environment Variables → добавь:**
   ```
   LOG_LEVEL=DEBUG
   ```

2. **Restart контейнера** (займёт 10-20 секунд)

3. **Открой Mini App** → попробуй загрузить слоты

4. **Dokploy → Logs** → скопируй строки с `DEBUG | validate_init_data` и всё после этого до следующего запроса

5. **Пришли сюда логи**

С DEBUG логами точно найду проблему за 1 минуту!
