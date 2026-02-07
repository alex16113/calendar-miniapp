# Диагностика проблем с Mini App в Telegram

## Симптом: белый экран при открытии Mini App в Telegram

### Проверка 1: Настройки BotFather

1. Открой @BotFather в Telegram
2. Отправь `/mybots`
3. Выбери своего бота
4. Нажми **Menu Button** (или **Bot Settings** → **Menu Button**)
5. Проверь, что URL указан правильно: `https://calendar.vpncfo.ru`
   - НЕ должно быть `/#/` в конце
   - Должен быть именно домен без пути
6. Если URL неправильный — исправь и сохрани

### Проверка 2: Домен и HTTPS

1. Открой в обычном браузере: https://calendar.vpncfo.ru
2. Проверь, что:
   - Сайт открывается (не 404)
   - HTTPS работает (зелёный замочек)
   - Нет ошибок сертификата

### Проверка 3: Логи Dokploy

1. Зайди в Dokploy → твоё приложение → **Logs**
2. При открытии Mini App в Telegram должны появиться строки:
   ```
   INFO:     10.0.1.4:xxxxx - "GET / HTTP/1.1" 200 OK
   INFO:     10.0.1.4:xxxxx - "GET /assets/index-xxx.css HTTP/1.1" 200 OK
   INFO:     10.0.1.4:xxxxx - "GET /assets/index-xxx.js HTTP/1.1" 200 OK
   ```
3. Если видишь **304 Not Modified** — это нормально (кеш), но если был белый экран раньше — нужно очистить кеш:
   - В Telegram: Settings → Advanced → Clear Cache → Clear Cache and Restart
   - Или переустанови приложение бота

### Проверка 4: JavaScript консоль (для продвинутых)

Если есть доступ к девтулзам в Telegram Desktop:

1. Открой Telegram Desktop
2. Нажми Cmd+Alt+I (Mac) или Ctrl+Shift+I (Windows/Linux)
3. Открой Mini App
4. Смотри вкладку Console на ошибки
5. Частые проблемы:
   - `Telegram is not defined` — скрипт SDK не загрузился
   - `401 Unauthorized` — проблема с initData (но это не должно ломать всё приложение)
   - CORS ошибки — проверь настройки CORS в `api/app.py`

### Проверка 5: Переменные окружения в Dokploy

Убедись, что в Dokploy заданы все обязательные env:

```bash
BOT_TOKEN=...
ADMIN_ID=...
BOT_WEBAPP_URL=https://calendar.vpncfo.ru  # важно!
```

### Проверка 6: Пересборка после изменений

После пуша в GitHub Dokploy должен автоматически пересобрать:

1. Зайди в Dokploy → Applications → твоё приложение
2. Если автодеплой не настроен — нажми **Deploy** вручную
3. Дождись завершения сборки (2-5 минут)
4. Проверь логи сборки на ошибки

### Проверка 7: Очистка кеша Telegram

Если всё выше проверено, но белый экран остался:

1. В Telegram: Settings → Advanced → Clear Cache
2. Нажми **Clear Cache** и **Restart**
3. Открой бота заново и попробуй открыть Mini App

### Если ничего не помогло

1. Проверь, что через обычный браузер https://calendar.vpncfo.ru работает
2. Проверь логи Dokploy на ошибки при запуске контейнера
3. Проверь, что порт 8000 пробрасывается правильно
4. Убедись, что домен `calendar.vpncfo.ru` резолвится на правильный IP

---

## Последние изменения (2026-02-07)

Исправлено:
- Инициализация `Telegram.WebApp.ready()` перенесена в `index.html` (до загрузки React)
- Добавлен `ErrorBoundary` для обработки ошибок в production
- Расширен CORS для поддержки всех Telegram origins (включая mobile WebView)

После этих изменений нужно:
1. Дождаться пересборки в Dokploy
2. Очистить кеш в Telegram
3. Попробовать открыть Mini App снова
