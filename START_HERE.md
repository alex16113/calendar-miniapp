# 👋 Старт для нового агента

**Дата:** 2026-02-07  
**Проект:** Smart Scheduler (Telegram Mini App)

---

## Текущий статус

✅ **Mini App работает:** https://calendar.vpncfo.ru  
✅ **Бот:** @google_calendar_booking1_bot  
✅ **Функционал:** запись на встречи, модерация, Google Calendar интеграция  

🔧 **Нужно доработать:** дизайн, UX, тестирование всех экранов

---

## Быстрый старт

### 1. Прочитай эти файлы (по порядку):

1. **NEXT_AGENT_PROMPT.md** — твоя задача, что делать дальше
2. **LESSONS_MINIAPP_DEBUG.md** — все проблемы и решения (чтобы не повторять ошибки)
3. **AGENT_HANDOFF.md** — полное описание проекта, архитектуры, всех этапов
4. **MINI_APP_ROADMAP.md** — Design Spec (как должен выглядеть дизайн)

### 2. Для контекста (опционально):

- **PROJECT_STEPS.md** — хронология всех изменений
- **CHANGELOG_2026_02_07.md** — что было сделано сегодня (деплой + отладка)
- **DEPLOY_DOKPLOY.md** — инструкция по деплою

### 3. Локальный запуск

```bash
# Backend
cd /Users/alex/Desktop/Calendar\ miniapp
source .venv/bin/activate
python run.py

# Frontend (в новом терминале)
cd mini-app
npm run dev
```

### 4. Тестирование в Telegram

1. Открой @google_calendar_booking1_bot
2. Нажми Menu Button (синяя кнопка внизу)
3. Проверь все экраны

---

## Твоя задача

**Цель:** доработать дизайн (Apple-like), протестировать, отполировать UX.

**Приоритет:**
1. Дизайн форм (Home, Booking, MyMeetings, Admin) по Design Spec
2. Loading states (спиннеры)
3. Пустые состояния ("Нет данных")
4. Сообщения об ошибках
5. Тестирование всех сценариев

**Детали:** см. `NEXT_AGENT_PROMPT.md`

---

## Структура проекта

```
/Users/alex/Desktop/Calendar miniapp/
├── api/                    # Backend (FastAPI)
│   ├── app.py             # Главный файл API
│   ├── deps.py            # Зависимости (валидация initData)
│   └── telegram_webapp.py # Валидация initData (HMAC + Ed25519)
├── mini-app/              # Frontend (React)
│   ├── src/
│   │   ├── pages/         # Экраны (Home, Booking, MyMeetings, Admin)
│   │   ├── api.ts         # API клиент
│   │   ├── App.tsx        # Роутинг
│   │   └── main.tsx       # Entry point
│   ├── index.html         # HTML (Telegram SDK инициализация)
│   └── index.css          # Глобальные стили (сейчас минимальные)
├── handlers/              # Бот (aiogram)
├── database/              # БД (SQLite)
├── services/              # Бизнес-логика (Google Calendar, слоты)
├── Dockerfile             # Multi-stage (Node → Python)
└── run.py                 # Entry point (бот + uvicorn)
```

---

## Что НЕ трогать

✋ **Не меняй без необходимости:**
- `api/telegram_webapp.py` — валидация initData (работает корректно)
- `api/deps.py` — зависимости API (работает)
- `mini-app/index.html` — инициализация Telegram SDK (критично!)
- `mini-app/src/api.ts` — логика sendRequest (передача initData)

🟢 **Можешь менять свободно:**
- Всё в `mini-app/src/pages/` — экраны (Home, Booking, MyMeetings, Admin)
- `mini-app/index.css` — глобальные стили
- Создавать новые компоненты в `mini-app/src/components/`
- Добавлять CSS модули, styled-components, или что угодно для стилей

---

## Важные моменты

### Telegram SDK
- Инициализируется в `index.html` (синхронно, до React)
- Доступен через `window.Telegram.WebApp`
- Используй `themeParams` для цветов, `colorScheme` для тёмной темы
- Haptic feedback: `window.Telegram.WebApp.HapticFeedback`

### initData
- Передаётся автоматически в `api.ts:sendRequest()`
- Не удаляй логику передачи в заголовке
- Если initData пустой — показываем инструкцию (уже реализовано в Home.tsx)

### Роутинг
- Используем HashRouter (`/#/path`)
- Fallback route `<Route path="*">` обязателен (уже есть)

### Валидация
- Поддерживает HMAC (старый формат) и Ed25519 (новый формат)
- Работает корректно, не трогай без острой необходимости

---

## Чеклист перед завершением

- [ ] Все экраны в Apple-like стиле
- [ ] Loading states добавлены
- [ ] Пустые состояния обработаны
- [ ] Ошибки API показываются пользователю
- [ ] Протестировано в Telegram (Menu Button)
- [ ] Проверены все сценарии (запись, мои заявки, админка)
- [ ] Деплой успешен (автодеплой на push в `main`)

---

## Полезные команды

### Докплой
```bash
# Логи контейнера
dokploy logs <app-id> -f

# Пересборка и рестарт
git push origin main  # автодеплой
```

### Git
```bash
# Коммит изменений
git add .
git commit -m "улучшение дизайна форм"
git push origin main
```

### NPM
```bash
cd mini-app
npm run dev      # dev server
npm run build    # production build
npm run preview  # preview production build
```

---

## Контакты и ссылки

- **Репо:** https://github.com/alex16113/calendar-miniapp
- **Домен:** https://calendar.vpncfo.ru
- **Бот:** @google_calendar_booking1_bot
- **Dokploy:** (спроси у пользователя URL панели)

---

**Удачи! 🚀**

*Если что-то непонятно — спрашивай пользователя. Все проблемы решены, теперь фокус на дизайне.*
