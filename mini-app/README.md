# Mini App (пользовательский)

React + Vite, открывается в Telegram WebApp.

## Локальная разработка

```bash
npm install
npm run dev
```

В другом терминале запусти бэкенд: из корня репо `python run.py`.

Vite проксирует `/slots`, `/booking`, `/my` на `http://localhost:8000`. Открой в браузере http://localhost:5173 — без Telegram initData запросы к API вернут 401; для проверки UI этого достаточно.

## Проверка в Telegram

1. Собери статику: `npm run build`.
2. Раздай `dist/` через тот же хост, что и API (например FastAPI StaticFiles на calendar.vpncfo.ru).
3. В BotFather укажи URL Mini App (например https://calendar.vpncfo.ru или с путём, где отдаётся index.html).
4. Открой бота → кнопка «Открыть» (Menu Button) или «Открыть приложение» в меню — откроется Mini App с валидным initData, «Мои заявки» и API будут работать.

## Роуты

- `/` — главная (ссылки на запись и мои заявки)
- `/#/book` — запись (пока заглушка)
- `/#/my` — мои заявки (список, отмена pending, ссылка в календарь для confirmed)
