# Диагностика загрузки в Telegram WebView

Добавлено детальное логирование на КАЖДОМ этапе загрузки.

---

## Что сейчас произойдёт после пересборки

### 1. Дождись пересборки Dokploy (2-3 минуты)

Зайди в Dokploy → Applications → `calendar-miniapp` → смотри Build Logs до `Successfully built`.

### 2. Открой Mini App через Telegram

**ВАЖНО:** Открывай через **Menu Button** (синяя кнопка внизу), НЕ через браузер!

1. Открой бота в Telegram
2. Нажми кнопку внизу (Menu Button)
3. Приложение откроется

---

## Что смотреть в Web Inspector

### Вариант А: Telegram Desktop (если есть)

1. **Открой Telegram Desktop**
2. **Включи Developer Tools:**
   - Mac: `Cmd + Alt + I`
   - Windows/Linux: `Ctrl + Shift + I`
3. **Открой вкладку Console**
4. **Открой бота → Menu Button**
5. **Смотри логи в Console**

### Вариант Б: Telegram iOS/Android (с компьютером)

#### Для iOS:
1. iPhone → Settings → Safari → Advanced → Web Inspector (включи)
2. Подключи iPhone к Mac через кабель
3. На Mac: Safari → Develop → [твой iPhone] → выбери WebView

#### Для Android:
1. Включи Developer Mode на Android
2. Settings → Developer Options → USB Debugging (включи)
3. Подключи к компьютеру
4. На компьютере: Chrome → `chrome://inspect` → найди WebView

---

## Что ты увидишь в Console

### Если всё ХОРОШО (приложение загружается):

```
[INIT] HTML loaded, checking Telegram SDK...
[INIT] Проверка Telegram SDK...
[INIT] Telegram SDK OK
[INIT] WebApp OK, вызов ready()...
[INIT] Ready/expand вызваны
[INIT] initData length: 234  ← ЧИСЛО ДОЛЖНО БЫТЬ > 0!
[INIT] Загрузка React...
[MAIN] main.tsx loaded, starting React...
[MAIN] Creating React root...
[MAIN] Rendering App...
[APP] App.tsx loaded
[APP] App component rendering
[API] Telegram object: exists
[API] WebApp object: exists
[API] initData length: 234  ← ТО ЖЕ ЧИСЛО
```

→ Если видишь ЭТО — приложение загружается правильно!

### Если ПЛОХО (ошибка загрузки):

Смотри, где останавливается:

#### 1. Останавливается на "ОШИБКА: Telegram SDK не загрузился!"
```
[INIT] Проверка Telegram SDK...
[INIT] ОШИБКА: Telegram SDK не загрузился!
```

**Причина:** Скрипт `telegram-web-app.js` не загрузился из-за:
- Блокировка сети/файрвола
- CSP (Content Security Policy) блокирует внешние скрипты
- Telegram WebView не поддерживает этот скрипт

**Решение:** Проверь Network tab — грузится ли `telegram-web-app.js`

#### 2. Останавливается на "initData length: 0"
```
[INIT] initData length: 0
[INIT] ВНИМАНИЕ: initData пустой (возможно открыто не через Menu Button)
```

**Причина:** Открыто НЕ через Menu Button, или Menu Button не настроен в BotFather.

**Решение:** См. `FIX_BOTFATHER.md`

#### 3. Останавливается на "[MAIN] main.tsx loaded..."
```
[INIT] Загрузка React...
[MAIN] main.tsx loaded, starting React...
← И дальше ничего нет
```

**Причина:** React не может загрузиться — проблема с JS модулями или импортами.

**Решение:** Проверь **Errors** в Console (красные строки)

#### 4. Красные ошибки в Console

Если видишь красные строки с `[GLOBAL ERROR]` или `Uncaught Error`:

```
[GLOBAL ERROR] Cannot find module 'react' ...
```

**Причина:** Проблема со сборкой или загрузкой JS файлов.

**Решение:** Проверь Network tab — все ли `.js` файлы загружаются со статусом 200

---

## Что смотреть в Network tab

1. Открой вкладку **Network** в DevTools
2. Открой Mini App
3. Смотри список запросов:

### Должно быть:

```
✅ calendar.vpncfo.ru/          200  document
✅ /assets/index-XXX.js          200  script
✅ /assets/index-XXX.css         200  stylesheet
✅ telegram-web-app.js           200  script (с telegram.org)
```

### Если что-то 404 или Failed:

```
❌ telegram-web-app.js           Failed
```

→ Telegram SDK не загружается! Пришли скриншот Network tab.

---

## Если вообще ничего нет в Console

Если Console ПУСТОЙ (нет ни одного лога `[INIT]`):

**Причина:** JavaScript вообще не выполняется в WebView.

**Возможные причины:**
1. Telegram WebView блокирует JS (маловероятно, но бывает)
2. Приложение не загружается (белый экран без HTML)
3. CSP блокирует inline scripts

**Что проверить:**
1. Смотри вкладку **Elements** — есть ли там HTML с `<div id="root">`?
2. Смотри **Console** — есть ли ошибки красным?
3. Смотри **Network** — грузятся ли файлы?

---

## Визуальные индикаторы (без DevTools)

Теперь приложение показывает статус прямо на экране (без консоли):

### Сразу после открытия увидишь:

1. **"Загрузка приложения..."** (первый экран)
2. Потом **"Загрузка..."** с текстом статуса внизу:
   - "Инициализация"
   - "Проверка Telegram SDK..."
   - "Telegram SDK OK"
   - "WebApp OK, вызов ready()..."
   - "initData length: XXX"
   - "Загрузка React..."
3. Потом должна загрузиться главная страница

### Если видишь красный текст с ошибкой:

Например:
```
Ошибка загрузки
Cannot read property 'WebApp' of undefined
```

→ Пришли скриншот этого экрана!

---

## Что мне прислать для диагностики

Выбери вариант в зависимости от того, что удалось сделать:

### Вариант 1: Есть доступ к Console (Desktop/инспектор)

Пришли **скриншот Console** после открытия Mini App, где видны строки с `[INIT]`, `[MAIN]`, `[APP]`.

### Вариант 2: Нет доступа к Console, но видишь экран

Пришли **скриншот экрана** Telegram с открытым Mini App:
- Если там текст статуса — что написано?
- Если белый экран — так и напиши
- Если ошибка красным — скриншот

### Вариант 3: Совсем ничего не получается

Напиши:
1. Какое устройство (iOS/Android/Desktop)?
2. Какая версия Telegram?
3. Что происходит при нажатии Menu Button? (белый экран / ничего / ошибка)

---

## Следующий шаг

**После пересборки Dokploy:**

1. Открой бота в Telegram (через Menu Button!)
2. Посмотри Console (если есть доступ) или экран
3. Пришли результат — логи или скриншот

С этой информацией точно найдём проблему!
