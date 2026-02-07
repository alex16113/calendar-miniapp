# Пошаговая инструкция: деплой Calendar Mini App в Dokploy

Репо: **https://github.com/alex16113/calendar-miniapp**, ветка **main**

---

## Шаг 1. Создать приложение

1. Открой веб-интерфейс Dokploy (обычно `https://your-dokploy-domain.com`)
2. В боковом меню выбери **Projects** или **Applications**
3. Нажми **"Create Application"** (или **"New Application"**, **"+ Add Application"** — зависит от версии)
4. Появится экран выбора типа приложения:
   - Выбери **"Docker"** (или **"Dockerfile"** / **"Build from Dockerfile"**)
   - НЕ выбирай Docker Compose (у нас один Dockerfile, не compose.yml)

---

## Шаг 2. Основные настройки (General / Settings)

На экране создания приложения заполни:

| Поле | Значение |
|------|----------|
| **Application Name** (имя) | `calendar-miniapp` (или как хочешь, латиница без пробелов) |
| **Description** (описание, опционально) | `Telegram бот + Mini App для записи на встречи` |

---

## Шаг 3. Подключить GitHub (Source / Git Repository)

### 3.1. Выбор источника

В разделе **Source** (или **Git**, **Repository**):

| Поле | Значение |
|------|----------|
| **Source Type** | Выбери **"GitHub"** (или **"Git Repository"**) |
| **Repository URL** | `https://github.com/alex16113/calendar-miniapp` |
| **Branch** | `main` |

### 3.2. Авторизация GitHub (если ещё не подключал)

- Если Dokploy попросит авторизацию: нажми **"Connect GitHub"** → войди в GitHub → разреши доступ Dokploy к репозиторию `alex16113/calendar-miniapp`.
- Dokploy получит права читать код для сборки.

### 3.3. Путь к Dockerfile

| Поле | Значение |
|------|----------|
| **Dockerfile Path** | `/Dockerfile` (или просто `Dockerfile`) — файл в корне репо |
| **Build Context** | `.` (точка — корень репо, обычно по умолчанию) |

---

## Шаг 4. Порт приложения (Ports / Networking)

В разделе **Ports** (или **Networking**, **Expose**):

| Поле | Значение | Пояснение |
|------|----------|-----------|
| **Container Port** (внутренний порт) | `8000` | Приложение внутри контейнера слушает 8000 |
| **Exposed Port** (наружу, опционально) | Оставь пустым или `8000` | Dokploy сам пробросит через прокси на домен |

**Важно**: не нужно вручную пробрасывать 8000:8000 на хост — Dokploy использует внутренний прокси. Просто укажи **Container Port = 8000**, чтобы Dokploy знал, куда слать трафик с домена.

---

## Шаг 5. Домен (Domains)

В разделе **Domains** (или **Custom Domains**, **Routing**):

1. Нажми **"Add Domain"** (или **"+ Domain"**)
2. Заполни:

| Поле | Значение |
|------|----------|
| **Domain** | `calendar.vpncfo.ru` |
| **Enable HTTPS** (или SSL) | Включи (галочка) — Dokploy автоматом получит Let's Encrypt сертификат |
| **Port** (если спрашивает) | `8000` (внутренний порт контейнера) |

3. Нажми **Save** или **Add**

**Важно**: DNS для `calendar.vpncfo.ru` должен указывать на IP сервера с Dokploy (A-запись `calendar.vpncfo.ru` → IP сервера). Если DNS ещё не настроен — сделай до деплоя, иначе Let's Encrypt не выдаст сертификат.

---

## Шаг 6. Volume для БД и OAuth (Volumes / Mounts)

В разделе **Volumes** (или **Mounts**, **Persistent Storage**):

1. Нажми **"Add Volume"** (или **"+ Mount"**)
2. Заполни:

| Поле | Значение | Пояснение |
|------|----------|-----------|
| **Type** | Выбери **"Volume"** (или **"Named Volume"**, **"Persistent Volume"**) | Dokploy создаст volume и сохранит данные между перезапусками |
| **Volume Name** (опционально) | `calendar-miniapp-data` (или любое имя) | Dokploy может сгенерировать само |
| **Mount Path** (путь в контейнере) | `/app/data` | Приложение пишет БД и OAuth в этот каталог |

3. Нажми **Save** или **Add**

**Альтернатива**: если хочешь "Bind Mount" (примонтировать конкретный каталог с хоста):
- Type: **"Bind Mount"**
- Host Path: `/var/dokploy/volumes/calendar-miniapp-data` (или куда хочешь на хосте)
- Container Path: `/app/data`

---

## Шаг 7. Переменные окружения (Environment Variables)

В разделе **Environment** (или **Env Variables**, **Configuration**):

1. Нажми **"Add Variable"** (или **"+ Env"**, или просто есть список полей)
2. Добавь каждую переменную по очереди (ниже — обязательные + рекомендуемые):

### Обязательные:

| Имя переменной | Значение | Пояснение |
|----------------|----------|-----------|
| `BOT_TOKEN` | Твой токен бота из @BotFather | Например `123456:ABCdef...` |
| `ADMIN_ID` | Твой Telegram user_id | Например `123456789` (числовой ID) |
| `BOT_WEBAPP_URL` | `https://calendar.vpncfo.ru` | URL для кнопки «Открыть приложение» + CORS |

### База данных и пути:

| Имя переменной | Значение |
|----------------|----------|
| `DB_PATH` | `/app/data/smart_scheduler.db` |

### Google Calendar (OAuth):

| Имя переменной | Значение | Пояснение |
|----------------|----------|-----------|
| `GOOGLE_AUTH_MODE` | `oauth` | Режим OAuth (если используешь OAuth вместо Service Account) |
| `CALENDAR_ID` | Твой Calendar ID | Например `alex@gmail.com` или `abc123@group.calendar.google.com` |
| `GOOGLE_OAUTH_CLIENT_SECRETS_PATH` | `/app/data/client_secrets.json` | Путь внутри контейнера |
| `GOOGLE_OAUTH_TOKEN_PATH` | `/app/data/token.json` | Путь внутри контейнера |

**Важно**: файлы `client_secrets.json` и `token.json` нужно положить в volume `/app/data` на сервере ДО первого запуска (см. Шаг 8).

### Рабочие часы и таймзона:

| Имя переменной | Значение | По умолчанию |
|----------------|----------|--------------|
| `TIMEZONE` | `Europe/Moscow` | (или твоя таймзона) |
| `WORK_START` | `11:00` | Начало рабочего дня |
| `WORK_END` | `18:00` | Конец рабочего дня |
| `BUFFER_HOURS` | `3` | Минимальное время до встречи (часы) |

### Опционально (если не задашь, будут дефолты):

| Имя переменной | Значение | По умолчанию |
|----------------|----------|--------------|
| `LOG_LEVEL` | `INFO` | Уровень логов |
| `PENDING_TTL_HOURS` | `24` | Автоотмена pending через N часов |
| `EXPIRE_CHECK_INTERVAL_SECONDS` | `60` | Интервал проверки истекших заявок |

3. Нажми **Save** после добавления всех переменных

---

## Шаг 8. Подготовить OAuth-файлы (перед деплоем)

### 8.1. Получить `client_secrets.json` из Google Cloud Console

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Проект → **APIs & Services** → **Credentials**
3. Найди OAuth 2.0 Client ID (тип **Desktop App** или **Web App**)
4. Нажми "Download JSON" → сохрани как `client_secrets.json`

### 8.2. Получить `token.json` (локально, потом скопируешь)

Если ещё нет `token.json`:

```bash
# На локальной машине (MacOS):
cd /Users/alex/Desktop/Calendar\ miniapp
source .venv/bin/activate
python scripts/google_oauth_init.py
```

- Откроется браузер → войди в Google → разреши доступ к календарю
- Скрипт сохранит `token.json` в корне проекта

### 8.3. Скопировать файлы на сервер в volume

Dokploy создал volume (например `/var/lib/docker/volumes/calendar-miniapp-data/_data` или `/var/dokploy/volumes/...`). Узнать точный путь:

**Через SSH на сервере:**

```bash
# Найти volume
docker volume inspect calendar-miniapp-data
# Вывод покажет "Mountpoint": "/var/lib/docker/volumes/календарь/_data"

# Скопировать файлы (с локальной машины через scp):
scp client_secrets.json your-user@your-server:/tmp/
scp token.json your-user@your-server:/tmp/

# На сервере переместить в volume:
sudo mv /tmp/client_secrets.json /var/lib/docker/volumes/calendar-miniapp-data/_data/
sudo mv /tmp/token.json /var/lib/docker/volumes/calendar-miniapp-data/_data/
sudo chown -R 1000:1000 /var/lib/docker/volumes/calendar-miniapp-data/_data/
```

**Альтернатива (если Dokploy даёт File Manager в UI)**:
- Зайди в Dokploy → твоё приложение → Volumes → открой файловый менеджер volume `calendar-miniapp-data` → загрузи `client_secrets.json` и `token.json`.

---

## Шаг 9. Запустить деплой

1. В Dokploy, на странице приложения **calendar-miniapp**, нажми **"Deploy"** (или **"Build & Deploy"**, **"Start Deployment"**)
2. Dokploy:
   - Склонирует репо с GitHub
   - Запустит `docker build` по Dockerfile (multi-stage: Node → сборка mini-app, Python → финальный образ)
   - Создаст контейнер, примонтирует volume `/app/data`, зададуст env
   - Запустит контейнер (CMD = `python run.py` → бот в фоне + uvicorn на :8000)
   - Настроит прокси: трафик с `https://calendar.vpncfo.ru` → контейнер :8000

3. Следи за логами сборки в Dokploy (раздел **Logs** или **Build Logs**)
   - Сборка займёт 2–5 минут (Node stage + pip install)
   - Если всё ОК — статус **"Running"** или **"Active"**

---

## Шаг 10. Проверка после деплоя

### 10.1. Health-check

Открой в браузере:

```
https://calendar.vpncfo.ru/health
```

Должен вернуться JSON: `{"status":"ok"}`

### 10.2. Главная Mini App

```
https://calendar.vpncfo.ru/
```

Должна открыться главная страница Mini App (заголовок «Запись. Календарь Алексея.», кнопки «Записаться», «Открыть список»).

### 10.3. Telegram

1. Открой бота в Telegram
2. Нажми кнопку внизу **"Открыть приложение"** (Menu Button) — должна открыться та же главная
3. Проверь флоу:
   - **Записаться** → выбор длительности → неделя → день → время → форма → отправка
   - **Мои заявки** → список твоих pending/confirmed
   - **Админка** (если твой `ADMIN_ID`) → список pending других, модерация

### 10.4. Логи (если что-то не работает)

В Dokploy → твоё приложение → **Logs** (или **Container Logs**):

- Должны быть строки:
  ```
  INFO:     Uvicorn running on http://0.0.0.0:8000
  Bot task started in background
  Serving Mini App static from /app/dist
  ```
- Если ошибки — смотри текст ошибки, обычно проблемы:
  - Не задан `BOT_TOKEN` или `ADMIN_ID`
  - Нет `token.json` в `/app/data` (бот упадёт при первой попытке обратиться к Google Calendar)
  - DNS домена ещё не пропагировался → HTTPS не работает

---

## Шаг 11. (Опционально) Настроить BotFather

Если ещё не сделал:

1. Открой @BotFather в Telegram
2. `/mybots` → выбери своего бота → **Menu Button**
3. Укажи URL: `https://calendar.vpncfo.ru`
4. Название кнопки (по умолчанию «Открыть приложение»)

Теперь у бота будет кнопка внизу, ведущая в Mini App.

---

## Готово!

После этих шагов у тебя:
- Контейнер с ботом + API + Mini App работает на `calendar.vpncfo.ru`
- БД и OAuth сохраняются в volume `/app/data`
- Бот в Telegram с кнопкой → Mini App
- HTTPS автоматически (Let's Encrypt через Dokploy)

Если что-то сломается — смотри логи в Dokploy, проверь env и volume.
