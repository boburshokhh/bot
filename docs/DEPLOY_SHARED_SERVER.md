# Деплой на общем Ubuntu-сервере (несколько проектов)

Пошаговая инструкция по развёртыванию Planning Bot на Ubuntu-сервере, где **уже работают другие проекты**. Сначала проверяем занятые порты, затем деплоим без конфликтов. У сервера есть **белый IP** и **домен** для webhook.

---

## Что понадобится

- Доступ по SSH к Ubuntu-серверу
- Домен (например `bot.yourdomain.com`) с **A-записью** на IP сервера
- Токен бота Telegram от [@BotFather](https://t.me/BotFather)

---

## Шаг 0 — Установить Docker (если ещё нет)

На сервере выполните:

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

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
```

**Важно:** после `usermod` выйдите из SSH и зайдите снова (или выполните `newgrp docker`), чтобы группа применилась.

Проверка:

```bash
docker --version
docker compose version
```

Git (если ещё не установлен):

```bash
sudo apt install -y git
```

---

## Шаг 1 — Проверить, какие порты свободны

На сервере выполните:

```bash
# Список всех слушающих TCP-портов
ss -tlnp
```

Или скрипт из репозитория (из корня проекта на сервере):

```bash
cd /opt/bot   # или каталог, куда клонируете проект
bash scripts/check-ports.sh
```

**Порты, которые использует бот:**

| Сервис     | Порт на хосте по умолчанию | Если занят — взять |
|------------|----------------------------|---------------------|
| App (HTTP) | 8000 или 8001             | Другой свободный, например 8002 |
| PostgreSQL | 5432 или 5433             | 5434, 5435… (только standalone) |
| Redis      | 6379 или 6380             | 6381, 6382… (только standalone) |
| Nginx      | 80, 443                   | Обычно **общие** с другими сайтами (новый server block) |

**Правило:** если порт есть в выводе `ss -tlnp` — он **занят**. В `docker-compose.yml` укажите **другой** порт на хосте (левая часть `"ХОСТ:КОНТЕЙНЕР"`). Внутри контейнеров порты 5432, 6379, 8000 не меняем.

---

## Шаг 2 — Выбрать тип деплоя

**Используйте только один вариант** — либо standalone, либо общая БД. Не запускайте оба compose подряд.

- **Standalone:** на этом сервере крутятся бот + свой PostgreSQL + Redis. Запуск: `docker compose up -d --build` (файл `docker-compose.yml`). При необходимости меняем порты на хосте (шаг 4).
- **Общая БД:** PostgreSQL и Redis на другом сервере. Запуск: `docker compose -f docker-compose.remote.yml up -d --build`. В `.env` задаём `DATABASE_URL` и `REDIS_URL` на тот сервер. Приложение по умолчанию слушает порт **8001** на хосте (чтобы не конфликтовать с занятым 8000).

---

## Шаг 3 — Клонировать проект и подготовить `.env`

```bash
sudo mkdir -p /opt/bot
sudo chown $USER:$USER /opt/bot
cd /opt/bot
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ> .
```

```bash
cp .env.example .env
nano .env
```

**Standalone** — пример `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
WEBHOOK_SECRET=ваша_случайная_строка_секрета
WEBHOOK_BASE_URL=https://bot.yourdomain.com

DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/planning_bot
REDIS_URL=redis://redis:6379/0

LOG_LEVEL=INFO
```

**Общая БД** — укажите `DATABASE_URL` и `REDIS_URL` на **другой сервер** (IP/хост и порт). Остальное так же: `TELEGRAM_BOT_TOKEN`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`.

Пароли делайте сложными; при standalone они должны совпадать с теми, что в `docker-compose.yml` (или задаются через переменные там).

---

## Шаг 4 — Задать порты на хосте в Docker (избежать конфликтов)

Если на шаге 1 оказалось, что заняты 8000, 5432 или 6379 — отредактируйте используемый compose-файл.

**Standalone** — правка `docker-compose.yml`:

```yaml
# Пример: приложение на 8002, Postgres на 5434, Redis на 6381
services:
  postgres:
    ports:
      - "5434:5432"    # хост:контейнер
  redis:
    ports:
      - "6381:6379"
  app:
    ports:
      - "8002:8000"    # Nginx будет проксировать на 127.0.0.1:8002
```

**Общая БД** — правка `docker-compose.remote.yml` только если нужно сменить порт приложения:

```yaml
services:
  app:
    ports:
      - "8002:8000"    # если 8000 занят
```

Запомните **порт на хосте** для приложения (например 8002). Он понадобится в Nginx: `proxy_pass http://127.0.0.1:8002`.

---

## Шаг 5 — Запустить бота

**Standalone:**

```bash
cd /opt/bot
docker compose up -d --build
```

**Общая БД:**

```bash
cd /opt/bot
docker compose -f docker-compose.remote.yml up -d --build
```

Один раз выполнить миграции (standalone или с любой машины, откуда есть доступ к БД):

```bash
docker compose exec app alembic upgrade head
```

Проверка:

```bash
docker compose ps
curl -s http://127.0.0.1:APP_PORT/health
```

Вместо `APP_PORT` подставьте порт приложения на хосте (например 8000 или 8002). Ожидается: `{"status":"ok"}`.

---

## Шаг 6 — Nginx + HTTPS (общие 80/443)

Остальные сайты продолжают работать через тот же Nginx на 80/443. Добавляем **новый server block** для бота.

Установите Nginx и Certbot, если ещё не стоят:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

Создайте конфиг (подставьте свой домен и `APP_PORT`):

```bash
sudo nano /etc/nginx/sites-available/planning-bot
```

Содержимое (укажите реальный порт приложения, например 8002):

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
        proxy_pass http://127.0.0.1:APP_PORT;
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
        proxy_pass http://127.0.0.1:APP_PORT;
        proxy_set_header Host $host;
    }
}
```

Замените **APP_PORT** на порт приложения на хосте (например 8002).

Получение SSL-сертификата:

```bash
sudo ln -sf /etc/nginx/sites-available/planning-bot /etc/nginx/sites-enabled/
# При первом запуске можно временно оставить только server { listen 80; server_name bot.yourdomain.com; ... }, затем:
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d bot.yourdomain.com
```

Если Certbot сам добавил блок с SSL — снова отредактируйте файл: добавьте `location /webhook` и `location /health` с `proxy_pass http://127.0.0.1:APP_PORT;`. Затем:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Шаг 7 — Настроить webhook в Telegram

Подставьте токен бота и домен:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://bot.yourdomain.com/webhook"
```

С секретным токеном (рекомендуется):

```bash
SECRET=$(openssl rand -hex 32)
echo $SECRET
# Добавьте WEBHOOK_SECRET=$SECRET в /opt/bot/.env

curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://bot.yourdomain.com/webhook\", \"secret_token\": \"$SECRET\"}"
```

Проверка:

```bash
curl -s https://bot.yourdomain.com/health
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## Чек-лист

- [ ] Установили Docker и Docker Compose (шаг 0), при необходимости — Git
- [ ] Выполнили `ss -tlnp` (или `scripts/check-ports.sh`), зафиксировали занятые порты
- [ ] Выбрали свободные порты на хосте для приложения (и для Postgres/Redis при standalone)
- [ ] Клонировали репозиторий, создали `.env` с токеном, URL webhook, URL БД/Redis
- [ ] При необходимости обновили порты в `docker-compose.yml` или `docker-compose.remote.yml`
- [ ] Запустили стек, выполнили `alembic upgrade head`, проверили `/health` по порту приложения
- [ ] Добавили server block в Nginx для `bot.yourdomain.com`, `proxy_pass` на нужный порт приложения
- [ ] Получили SSL через Certbot, перезагрузили Nginx
- [ ] Установили webhook через `setWebhook`, проверили через `getWebhookInfo` и сообщением боту

---

## Решение проблем

| Проблема | Что проверить |
|----------|----------------|
| Порт уже занят | `ss -tlnp`; сменить порт на хосте в compose и в Nginx `proxy_pass`. |
| 502 Bad Gateway | Контейнер приложения запущен; порт в `proxy_pass` совпадает с портом приложения; `curl http://127.0.0.1:APP_PORT/health` отвечает. |
| Webhook не приходят | В `getWebhookInfo` указан HTTPS URL; Nginx проксирует `/webhook` на приложение; фаервол разрешает 80/443. |

Подробнее (фаервол, логи, Celery) — в [DEPLOYMENT_UBUNTU_WEBHOOK.md](DEPLOYMENT_UBUNTU_WEBHOOK.md).
