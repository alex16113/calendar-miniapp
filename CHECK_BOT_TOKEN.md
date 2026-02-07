# ВАЖНО: Проверь BOT_TOKEN!

## Проблема может быть в неправильном токене

HMAC не совпадает → возможно, `BOT_TOKEN` в Dokploy неправильный.

---

## Как проверить (2 минуты)

### 1. Получи правильный токен

1. Открой **@BotFather** в Telegram
2. Отправь `/mybots`
3. Выбери своего бота (@google_calendar_booking1_bot)
4. Нажми **API Token**
5. Скопируй токен (выглядит как `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Проверь токен в Dokploy

1. Dokploy → Applications → `calendar-miniapp`
2. **Environment Variables**
3. Найди `BOT_TOKEN`
4. **Сравни** с токеном из BotFather

### 3. Если не совпадает — исправь!

1. Вставь правильный токен в `BOT_TOKEN`
2. **Save**
3. **Restart** контейнера
4. Дождись запуска
5. Открой Mini App
6. **Должно заработать!** ✅

---

## Как понять, что токен правильный?

В логах при старте бота должно быть:
```
INFO | bot | Authorized as bot
INFO | bot | Run polling for bot @google_calendar_booking1_bot id=8486580213
```

Если бот **запускается** и **отвечает на /start** в чате — токен правильный.

Но для валидации initData нужен **ТОЧНО ТОТ ЖЕ токен**, который использовался при создании Mini App в BotFather.

---

## Если токен правильный, но HMAC всё равно не совпадает

Тогда проблема в алгоритме валидации (Telegram изменил формат).

В этом случае используй временное решение из `QUICK_FIX.md`:
```
DISABLE_INIT_DATA_CHECK=1
```

---

## СНАЧАЛА проверь токен!

Это займёт 2 минуты, но может сразу решить проблему.

1. @BotFather → /mybots → твой бот → API Token
2. Dokploy → Environment Variables → BOT_TOKEN
3. Сравни
4. Если не совпадает → исправь и Restart

Если совпадает → используй QUICK_FIX.md (временное отключение проверки).
