# Инструкция: исправление белого экрана в Telegram Mini App

## Что было сделано

Исправлены 3 критические проблемы:

1. **Инициализация Telegram SDK** — перенесена из React в `index.html`, чтобы срабатывала до загрузки приложения
2. **CORS** — расширен для поддержки всех Telegram origins (iOS/Android WebView)
3. **Обработка ошибок** — добавлен ErrorBoundary для диагностики проблем

Код запушен в GitHub → Dokploy пересоберёт автоматически.

---

## Что делать ПРЯМО СЕЙЧАС

### Шаг 1: Дождись пересборки в Dokploy

1. Открой Dokploy: https://твой-dokploy-домен/
2. Зайди в Applications → `calendar-miniapp`
3. Смотри логи сборки (Build Logs)
4. Дождись сообщения типа:
   ```
   Successfully built ...
   Successfully tagged ...
   Container started
   ```
5. Это займёт 2-5 минут

### Шаг 2: Проверь BotFather

1. Открой @BotFather в Telegram
2. `/mybots` → выбери своего бота
3. **Menu Button** (или Bot Settings → Menu Button)
4. Убедись, что URL: `https://calendar.vpncfo.ru`
   - БЕЗ `/#/` в конце
   - Просто домен
5. Если нет — исправь и сохрани

### Шаг 3: Очисти кеш Telegram

**В Telegram (iOS/Android):**
1. Settings → Advanced → Clear Cache
2. Нажми "Clear Cache" и "Restart"

**В Telegram Desktop:**
1. Settings → Advanced → Manage local storage
2. Clear all

### Шаг 4: Проверь Mini App

1. Открой бота в Telegram
2. Нажми кнопку внизу "Открыть приложение"
3. Должна открыться главная страница с заголовком:
   ```
   Запись. Календарь Алексея.
   ```

---

## Если всё ещё белый экран

### Диагностика через браузер

1. Открой в обычном браузере: https://calendar.vpncfo.ru
2. Если НЕ открывается — проблема с деплоем:
   - Проверь логи контейнера в Dokploy
   - Убедись, что контейнер запущен (Status: Running)
   - Проверь переменные окружения (BOT_WEBAPP_URL)

3. Если ОТКРЫВАЕТСЯ в браузере, но НЕ в Telegram:
   - Проверь логи Dokploy при попытке открыть в Telegram
   - Должны быть запросы к `/`, `/assets/...`
   - Если запросов нет — проблема в BotFather URL

### Логи для диагностики

В Dokploy → Logs смотри на запросы при открытии Mini App:

**Хорошие логи:**
```
INFO: Application startup complete
INFO: 10.0.1.4:xxxxx - "GET / HTTP/1.1" 200 OK
INFO: 10.0.1.4:xxxxx - "GET /assets/index-xxx.js HTTP/1.1" 200 OK
```

**Плохие логи (нет запросов вообще):**
- Проблема в URL в BotFather
- Или проблема с DNS домена

**Ошибки в JavaScript (если видишь в консоли):**
- Теперь должен показываться ErrorBoundary с текстом ошибки
- Пришли скрин ошибки

---

## Проверочный список

- [ ] Код запушен в GitHub (уже сделано)
- [ ] Dokploy пересобрал образ (жди 2-5 мин)
- [ ] BotFather → Menu Button → `https://calendar.vpncfo.ru`
- [ ] Очистил кеш в Telegram
- [ ] Перезапустил Telegram
- [ ] Открыл бота и нажал "Открыть приложение"

---

## Если ничего не помогло

Пришли:
1. Скриншот экрана в Telegram (белый экран или ошибка)
2. Логи из Dokploy за последние 5 минут
3. Скрин настроек в BotFather (Menu Button URL)

Полная документация по диагностике: `TROUBLESHOOT_MINIAPP.md`
