# Полный гайд: деплой на Ubuntu и настройка Webhook

Пошаговая инструкция по развёртыванию Telegram Planning Bot на Ubuntu-сервере (в том числе на втором/параллельном сервере рядом с основным проектом) и настройке webhook.

---

## Содержание

- **Деплой на сервер с другими проектами:** [DEPLOY_SHARED_SERVER.md](DEPLOY_SHARED_SERVER.md) — проверка занятых портов и пошаговый деплой без конфликтов.

1. [Варианты деплоя](#1-варианты-деплоя)
2. [Подготовка Ubuntu-сервера](#2-подготовка-ubuntu-сервера)
3. [Деплой: второй сервер со своей БД (standalone)](#3-деплой-второй-сервер-со-своей-бд-standalone)
4. [Деплой: второй сервер с общей БД основного проекта](#4-деплой-второй-сервер-с-общей-бд-основного-проекта)
5. [Nginx + HTTPS для webhook](#5-nginx--https-для-webhook)
6. [Создание и настройка Webhook](#6-создание-и-настройка-webhook)
7. [Проверка и отладка](#7-проверка-и-отладка)
8. [Сервер только в локальной сети (без белого IP)](#8-сервер-только-в-локальной-сети-без-белого-ip)
9. [Что делать для запуска бота (после настройки)](#что-делать-для-запуска-бота-после-успешной-настройки)

---

## 1. Варианты деплоя

| Вариант | Описание |
|--------|----------|
| **Standalone** | Второй сервер со своими PostgreSQL, Redis и приложением. Полностью независим от основного. |
| **Общая БД** | Второй сервер только с приложением (и при необходимости Celery). PostgreSQL и Redis — на основном сервере. |

Ниже описаны оба варианта.

---

## 2. Подготовка Ubuntu-сервера

Выполняйте на **новом** Ubuntu-сервере (или на том, где ещё нет бота).

### 2.1. Обновление системы

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2. Установка Docker и Docker Compose

```bash
# Зависимости
sudo apt install -y ca-certificates curl gnupg

# Репозиторий Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Текущий пользователь в группу docker (чтобы не писать sudo каждый раз)
sudo usermod -aG docker $USER
# Выйдите и зайдите снова в SSH или выполните: newgrp docker
```

### 2.3. Установка Git (если ещё нет)

```bash
sudo apt install -y git
```

### 2.4. Домен и DNS (для webhook)

- Привяжите домен (например `bot.yourdomain.com`) к IP вашего сервера (A-запись).
- Webhook Telegram работает только по **HTTPS**, поэтому домен обязателен для продакшена.

---

## 3. Деплой: второй сервер со своей БД (standalone)

Подходит, если бот должен быть полностью отделён от основного проекта.

### Шаг 3.1. Клонирование и каталог

```bash
cd /opt   # или /home/youruser — как принято у вас
sudo mkdir -p /opt/bot
sudo chown $USER:$USER /opt/bot
cd /opt/bot
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ> .
# или скопируйте проект через scp/rsync
```

### Шаг 3.2. Файл окружения `.env`

```bash
cp .env.example .env
nano .env
```

Заполните (для standalone все сервисы на этом же сервере):

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
WEBHOOK_SECRET=your_random_secret_string
WEBHOOK_BASE_URL=https://bot.yourdomain.com

# Database (внутри Docker — имена сервисов postgres/redis)
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/planning_bot
REDIS_URL=redis://redis:6379/0

LOG_LEVEL=INFO
```

Пароли замените на свои; они должны совпадать с теми, что в `docker-compose.yml` (или задайте в `docker-compose` через переменные).

### Шаг 3.3. Запуск контейнеров

```bash
cd /opt/bot
docker compose up -d --build
```

### Шаг 3.4. Миграции (если не в CMD образа)

В Dockerfile уже есть `alembic upgrade head` в CMD; при необходимости выполнить вручную:

```bash
docker compose exec app alembic upgrade head
```

### Шаг 3.5. Проверка

```bash
docker compose ps
curl -s http://localhost:8000/health
# Должно вернуть: {"status":"ok"}
```

Дальше — пункты **5 (Nginx + HTTPS)** и **6 (Webhook)**.

---

## 4. Деплой: второй сервер с общей БД основного проекта

Бот работает на втором сервере, а PostgreSQL и Redis — на основном Ubuntu-сервере.

### Шаг 4.1. На основном сервере: доступ к PostgreSQL и Redis

- **PostgreSQL:** откройте порт 5432 для IP второго сервера и создайте пользователя/БД при необходимости:
  ```bash
  # На основном сервере (пример для ufw)
  sudo ufw allow from IP_ВТОРОГО_СЕРВЕРА to any port 5432
  sudo ufw allow from IP_ВТОРОГО_СЕРВЕРА to any port 6379
  sudo ufw reload
  ```
- В `pg_hba.conf` добавьте строку для доступа с IP второго сервера и выполните `sudo systemctl reload postgresql`.
- **Redis:** в `redis.conf` привяжите к `0.0.0.0` или к внутреннему IP и задайте `requirepass`, если нужна авторизация. Откройте порт 6379 для второго сервера.

### Шаг 4.2. На втором сервере: только приложение

Создайте отдельный `docker-compose.override.yml` или новый файл (например `docker-compose.remote.yml`), чтобы не поднимать локальные postgres/redis:

**Вариант A: override без postgres/redis**

В каталоге проекта создайте `docker-compose.remote.yml`:

```yaml
# docker-compose.remote.yml — только app + celery, БД на основном сервере
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://user:password@IP_ОСНОВНОГО_СЕРВЕРА:5432/planning_bot
      REDIS_URL: redis://:REDIS_PASSWORD@IP_ОСНОВНОГО_СЕРВЕРА:6379/0
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      WEBHOOK_SECRET: ${WEBHOOK_SECRET:-}
      WEBHOOK_BASE_URL: ${WEBHOOK_BASE_URL:-}
    restart: unless-stopped

  celery_worker:
    build: .
    command: celery -A src.scheduler.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://user:password@IP_ОСНОВНОГО_СЕРВЕРА:5432/planning_bot
      REDIS_URL: redis://:REDIS_PASSWORD@IP_ОСНОВНОГО_СЕРВЕРА:6379/0
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
    depends_on:
      - app
    restart: unless-stopped

  celery_beat:
    build: .
    command: celery -A src.scheduler.celery_app beat --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://user:password@IP_ОСНОВНОГО_СЕРВЕРА:5432/planning_bot
      REDIS_URL: redis://:REDIS_PASSWORD@IP_ОСНОВНОГО_СЕРВЕРА:6379/0
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
    depends_on:
      - celery_worker
    restart: unless-stopped
```

В `.env` на втором сервере укажите те же `DATABASE_URL` и `REDIS_URL` (на IP основного сервера), а также `TELEGRAM_BOT_TOKEN`, `WEBHOOK_BASE_URL`, при необходимости `WEBHOOK_SECRET`.

На **втором** сервере поднимать только приложение (без своих postgres/redis). Запуск:

```bash
docker compose -f docker-compose.remote.yml up -d --build
```

Файл `docker-compose.remote.yml` в корне проекта описывает только сервисы `app`, `celery_worker`, `celery_beat`; PostgreSQL и Redis не запускаются на этом сервере.

**Вариант B: вынести URL в .env**

В `.env` на втором сервере:

```env
TELEGRAM_BOT_TOKEN=...
WEBHOOK_BASE_URL=https://bot.yourdomain.com
WEBHOOK_SECRET=...
DATABASE_URL=postgresql+asyncpg://user:password@IP_ОСНОВНОГО:5432/planning_bot
REDIS_URL=redis://:password@IP_ОСНОВНОГО:6379/0
```

И в `docker-compose.remote.yml` используйте переменные: `DATABASE_URL: ${DATABASE_URL}`, `REDIS_URL: ${REDIS_URL}`.

### Шаг 4.3. Миграции

Миграции достаточно выполнить один раз — на основном сервере (где крутится БД) или один раз с любого места, где есть доступ к этой БД:

```bash
docker compose exec app alembic upgrade head
```

Дальше — **Nginx + HTTPS** и **Webhook**.

---

## 5. Nginx + HTTPS для webhook

Telegram отправляет обновления только на **HTTPS**. Нужны Nginx и сертификат (например Let's Encrypt).

### Шаг 5.1. Установка Nginx и Certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Шаг 5.2. Конфиг Nginx для бота

Создайте конфиг (замените `bot.yourdomain.com` на свой домен):

```bash
sudo nano /etc/nginx/sites-available/planning-bot
```

Содержимое:

```nginx
server {
    listen 80;
    server_name bot.yourdomain.com;
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name bot.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/bot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.yourdomain.com/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

### Шаг 5.3. Получение SSL-сертификата

Сначала можно поставить временный конфиг только на 80 порт для выдачи сертификата:

```bash
# Временно только HTTP
sudo nano /etc/nginx/sites-available/planning-bot
# Оставьте только server { listen 80; server_name bot.yourdomain.com; location / { return 200 'ok'; add_header Content-Type text/plain; } }
sudo ln -sf /etc/nginx/sites-available/planning-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d bot.yourdomain.com
```

Certbot сам добавит SSL-блок. Либо отредактируйте конфиг как в шаге 5.2 и снова выполните:

```bash
sudo certbot --nginx -d bot.yourdomain.com
```

Включите сайт и перезагрузите Nginx:

```bash
sudo ln -sf /etc/nginx/sites-available/planning-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Шаг 5.4. Автообновление сертификата

```bash
sudo certbot renew --dry-run
# Таймер уже должен быть: systemctl list-timers | grep certbot
```

---

## 6. Создание и настройка Webhook

### 6.1. Что такое webhook

Вместо long polling сервер Telegram сам отправляет обновления (сообщения, кнопки и т.д.) на ваш HTTPS URL. Эндпоинт в проекте: **POST /webhook**.

### 6.2. Установка webhook (одна команда)

Подставьте свой токен и домен:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://bot.yourdomain.com/webhook"
```

Пример ответа при успехе:

```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

### 6.3. Secret token (рекомендуется)

Чтобы только Telegram мог слать запросы на ваш /webhook, задайте секретный токен при установке webhook:

```bash
# Сгенерируйте случайную строку, например:
SECRET=$(openssl rand -hex 32)
echo $SECRET
```

Установите webhook с этим секретом:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://bot.yourdomain.com/webhook\", \"secret_token\": \"$SECRET\"}"
```

В `.env` на сервере добавьте (или используйте существующий `WEBHOOK_SECRET`):

```env
WEBHOOK_SECRET=ваш_секрет_из_SECRET
```

В коде бота нужно проверять заголовок `X-Telegram-Bot-Api-Secret-Token`: если он задан в настройках бота, сравнивать с `WEBHOOK_SECRET` и при несовпадении возвращать 403. В текущей версии проекта проверка опциональна; при желании её можно добавить в `main.py` (см. раздел 6.7).

### 6.4. Проверка текущего webhook

```bash
curl -s "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

Ответ содержит `url` и при наличии — `secret_token`.

### 6.5. Удаление webhook (переход на long polling или смена URL)

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook"
```

После этого можно снова вызвать `setWebhook` с новым URL или запускать бота в режиме long polling.

### 6.6. Краткая шпаргалка по API webhook

| Действие        | Метод/URL |
|-----------------|-----------|
| Установить      | `POST https://api.telegram.org/bot<TOKEN>/setWebhook` с `url` (и опционально `secret_token`) |
| Узнать текущий  | `GET https://api.telegram.org/bot<TOKEN>/getWebhookInfo` |
| Удалить         | `POST https://api.telegram.org/bot<TOKEN>/deleteWebhook` |

### 6.7. (Опционально) Проверка secret_token в приложении

Чтобы отклонять запросы без правильного заголовка, в `src/main.py` в обработчике `/webhook` можно добавить:

```python
# В начале обработчика webhook, после получения request:
secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
if settings.webhook_secret and secret_header != settings.webhook_secret:
    return JSONResponse(status_code=403, content={"ok": False})
```

Тогда в `.env` обязательно задайте `WEBHOOK_SECRET` тем же значением, что и `secret_token` в `setWebhook`.

---

## 7. Проверка и отладка

### 7.1. Локальная проверка

```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/webhook -H "Content-Type: application/json" -d '{}'
# В логах может быть ошибка разбора Update — это нормально для пустого тела
```

### 7.2. Внешний HTTPS

```bash
curl -s https://bot.yourdomain.com/health
```

### 7.3. Логи приложения

```bash
docker compose logs -f app
```

### 7.4. Логи Nginx

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 7.5. Типичные проблемы

| Проблема | Что проверить |
|----------|----------------|
| 502 Bad Gateway | Приложение слушает 8000, `proxy_pass` на `127.0.0.1:8000`, контейнер запущен. |
| Webhook не срабатывает | HTTPS, URL точно `https://..../webhook`, `setWebhook` выполнен, `getWebhookInfo` показывает этот URL. |
| SSL ошибки | Сертификат для нужного домена, срок действия, перезагрузка Nginx после certbot. |

---

## 8. Сервер только в локальной сети (без белого IP)

Если сервер доступен только из локальной сети (например 192.168.x.x), Telegram не сможет доставить webhook. Есть два варианта.

### Вариант A: Long polling (рекомендуется — ничего не пробрасывать)

Бот сам опрашивает Telegram за обновления. Домен, HTTPS и webhook **не нужны**.

1. **Удалите webhook**, если он был установлен:
   ```bash
   curl -X POST "https://api.telegram.org/bot<ТОКЕН>/deleteWebhook"
   ```

2. **Запустите контейнеры в режиме polling** (вместо FastAPI/webhook):
   ```bash
   cd /opt/bot
   docker compose down
   docker compose -f docker-compose.yml -f docker-compose.polling.yml up -d --build
   ```

3. В `.env` достаточно `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`. `WEBHOOK_BASE_URL` можно не указывать.

4. Проверка: напишите боту в Telegram; в логах должно быть `Long polling started`:
   ```bash
   docker compose logs -f app
   ```

Celery (утренние/вечерние уведомления) продолжает работать как раньше. Порт 8001 на хосте не используется.

### Вариант B: Туннель (ngrok) — оставить webhook

Туннель даёт вашему серверу временный публичный HTTPS-адрес. Telegram шлёт обновления на этот адрес, ngrok перенаправляет их на `localhost:8001`. Да, это решает проблему «сервер только в локальной сети».

#### Шаг 1. Бот должен работать в режиме webhook (порт 8001)

Не используйте `docker-compose.polling.yml`. Запустите обычный стек:

```bash
cd /opt/bot
docker compose down
docker compose up -d --build
```

Проверьте, что приложение отвечает локально:

```bash
curl -s http://localhost:8001/health
# Должно вернуть: {"status":"ok"}
```

#### Шаг 2. Регистрация в ngrok и токен

1. Зайдите на [ngrok.com](https://ngrok.com) и зарегистрируйтесь (бесплатно).
2. В личном кабинете: **Your Authtoken** — скопируйте токен.
3. На сервере добавьте токен (подставьте свой):

```bash
ngrok config add-authtoken ВАШ_ТОКЕН_ИЗ_КАБИНЕТА
```

Если `ngrok` ещё не установлен, сначала выполните шаг 3.

#### Шаг 3. Установка ngrok на Ubuntu

```bash
# Зависимости
sudo apt update
sudo apt install -y curl apt-transport-https

# Репозиторий ngrok (официальный)
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update
sudo apt install -y ngrok

# Токен (если ещё не делали)
ngrok config add-authtoken ВАШ_ТОКЕН
```

#### Шаг 4. Запуск туннеля на порт 8001

**Вручную (для проверки):**

```bash
ngrok http 8001
```

В терминале появится строка вида:

```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:8001
```

Скопируйте `https://abc123.ngrok-free.app` — это ваш публичный URL. Не закрывайте этот терминал (пока туннель работает, бот будет получать webhook).

**Чтобы отключение экрана/SSH не останавливало туннель** — настройте ngrok как службу (шаг 6). Тогда сайт и бот работают независимо от того, закрыт терминал или нет.

#### Шаг 5. Установка webhook в Telegram

Подставьте свой токен бота и URL из вывода ngrok (без слэша в конце, путь `/webhook` добавится):

```bash
curl -X POST "https://api.telegram.org/botВАШ_ТОКЕН_БОТА/setWebhook?url=https://abc123.ngrok-free.app/webhook"
```

Успешный ответ: `{"ok":true,"result":true,...}`. Проверка:

```bash
curl -s "https://api.telegram.org/botВАШ_ТОКЕН_БОТА/getWebhookInfo"
```

В ответе должен быть `"url":"https://....ngrok-free.app/webhook"`. Напишите боту в Telegram — ответы должны приходить.

#### Шаг 6. Туннель как служба — отключённый экран не мешает работе

Если запускать ngrok вручную в терминале, после закрытия SSH туннель остановится и бот перестанет получать обновления. Чтобы **сайт и бот работали без открытого экрана**, поднимите ngrok как systemd-сервис: он будет работать в фоне и после перезагрузки сервера.

1. Создайте файл службы:

```bash
sudo nano /etc/systemd/system/ngrok.service
```

2. Вставьте (порт 8001 — как у вашего приложения):

```ini
[Unit]
Description=ngrok tunnel for Telegram bot webhook
After=network.target docker.service

[Service]
Type=simple
ExecStart=/usr/bin/ngrok http 8001 --log=stdout
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Сохраните: Ctrl+O, Enter, Ctrl+X.

3. Включите и запустите службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok
sudo systemctl start ngrok
sudo systemctl status ngrok
```

Должно быть `active (running)`. После этого можно закрыть SSH — туннель продолжит работать.

4. Узнать текущий URL туннеля (нужен для setWebhook):

```bash
curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"https://[^"]*"' | head -1
```

Или откройте в браузере на ПК (если есть доступ к серверу по SSH с пробросом): `http://127.0.0.1:4040` — там будет указан публичный URL. Подставьте его в setWebhook (шаг 5).

**Важно:** при бесплатном ngrok URL может меняться после перезапуска службы или сервера. Тогда снова возьмите URL (команда выше или 4040) и выполните `setWebhook` с новым URL. Постоянный домен — у платного ngrok или Cloudflare Tunnel.

#### Шаг 6.1. Автообновление webhook при смене URL ngrok

В проекте есть скрипт, который сам получает текущий URL туннеля и обновляет webhook в Telegram.

**Вручную** (после перезагрузки сервера или перезапуска ngrok):

```bash
sudo chmod +x /opt/bot/scripts/update-webhook.sh
/opt/bot/scripts/update-webhook.sh
```

Скрипт читает `TELEGRAM_BOT_TOKEN` из `/opt/bot/.env`, ждёт появления туннеля в API ngrok (до 60 сек) и вызывает `setWebhook`.

**Автоматически после каждой загрузки сервера:**

Служба `telegram-webhook-update` один раз запускается после ngrok и обновляет webhook.

```bash
sudo cp /opt/bot/scripts/telegram-webhook-update.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable telegram-webhook-update.service
```

После перезагрузки сервера сначала поднимется ngrok, затем выполнится обновление webhook. Если вы только перезапустили ngrok вручную (`sudo systemctl restart ngrok`), один раз выполните:

```bash
sudo systemctl start telegram-webhook-update.service
```

#### Кратко: что делает туннель

| Кто              | Действие |
|------------------|----------|
| Telegram         | Шлёт POST на `https://xxxx.ngrok-free.app/webhook` |
| ngrok (в интернете) | Принимает запрос и пересылает на ваш сервер |
| Ваш сервер       | Получает запрос на `localhost:8001/webhook`, бот обрабатывает |

Домен и белый IP серверу не нужны — всё решает туннель.

**Cloudflare Tunnel:** даёт постоянный поддомен (например `bot.ваш-домен.com`) и не требует платного ngrok; настройка дольше — см. [Cloudflare Zero Trust](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/).

---

## Что делать для запуска бота (после успешной настройки)

Когда всё один раз настроено (Docker, ngrok как служба, webhook), для **запуска бота** достаточно следующего.

### Вариант: бот через туннель (ngrok), сервер только в локальной сети

1. **Запустить контейнеры бота**
   ```bash
   cd /opt/bot
   docker compose up -d
   ```

2. **Убедиться, что туннель ngrok работает** (если настроен как служба — уже запущен)
   ```bash
   sudo systemctl start ngrok
   sudo systemctl status ngrok
   ```

3. **Узнать URL туннеля** (если не помните или он мог измениться)
   ```bash
   curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*"' | head -1
   ```
   Скопируйте значение `https://....ngrok-free.app` (без кавычек).

4. **Установить webhook** (подставьте токен бота и URL из шага 3)
   ```bash
   curl -X POST "https://api.telegram.org/botВАШ_ТОКЕН/setWebhook?url=https://ВАШ_URL_ИЗ_NGROK/webhook"
   ```

5. **Проверить**
   - Написать боту в Telegram — должен ответить.
   - Логи: `docker compose logs -f app`

После перезагрузки сервера: Docker-контейнеры и служба ngrok поднимутся сами (если включены `enable`). Если URL ngrok изменился — либо снова выполните шаги 3 и 4, либо один раз запустите скрипт обновления webhook: `sudo /opt/bot/scripts/update-webhook.sh` (или включите службу `telegram-webhook-update.service`, см. раздел 8, шаг 6.1).

### Вариант: бот через long polling (без туннеля)

1. Запустить в режиме polling:
   ```bash
   cd /opt/bot
   docker compose -f docker-compose.yml -f docker-compose.polling.yml up -d
   ```
2. Webhook не нужен. Проверка: написать боту в Telegram, смотреть логи: `docker compose logs -f app`.

### Вариант: бот с белым IP и доменом (Nginx + HTTPS)

1. `cd /opt/bot && docker compose up -d`
2. Nginx и SSL уже настроены. Webhook один раз установлен на `https://ваш-домен/webhook`.
3. Проверка: написать боту, при необходимости смотреть логи `app`.

---

## Краткий чеклист деплоя

- [ ] Ubuntu обновлён, установлены Docker (и Docker Compose), Git, Nginx, Certbot.
- [ ] Домен направлен на сервер (A-запись).
- [ ] Проект склонирован/скопирован, `.env` заполнен (токен, URL БД/Redis, `WEBHOOK_BASE_URL`).
- [ ] Запущены контейнеры (`docker compose up -d` или с `docker-compose.remote.yml` для второго сервера).
- [ ] Миграции выполнены (`alembic upgrade head`).
- [ ] Nginx настроен, SSL получен, проксирование на `127.0.0.1:8000` для `/webhook` и `/health`.
- [ ] Webhook установлен: `setWebhook` с URL `https://ваш-домен/webhook`, при необходимости с `secret_token`.
- [ ] В Telegram отправлено сообщение боту и проверены логи `app`.

После этого бот на Ubuntu (в том числе на втором/параллельном сервере с общей или своей БД) и webhook готовы к работе.
