# Настройка домена под проект и сервер

Пошаговая настройка домена для Planning Bot на вашем сервере: DNS → Nginx → HTTPS → webhook.

---

## Что нужно

- **Домен** (например `me-bobur.uz` или любой другой)
- **Доступ к DNS** домена (панель регистратора, Cloudflare и т.п.)
- **Сервер** с белым IP, куда будет указывать домен
- На сервере уже запущен проект (Docker, приложение слушает порт **8001** на хосте)

---

## Шаг 1. DNS — направить домен на сервер

### 1.1. Узнать публичный IP сервера

На сервере выполните:

```bash
curl -s ifconfig.me
```

Или посмотрите IP в панели хостинга (VPS/VM).

### 1.2. Создать A-запись

В панели управления DNS вашего домена добавьте запись:

| Тип | Имя (Host) | Значение (Target)     | TTL   |
|-----|------------|------------------------|-------|
| **A** | `bot` или `@` | **IP_ВАШЕГО_СЕРВЕРА** | 300   |

- Если **имя** = `bot` → адрес будет **https://bot.ваш-домен.uz**
- Если **имя** = `@` (или пусто) → адрес будет **https://ваш-домен.uz**

Сохраните изменения. Распространение DNS — от 1–2 минут до 24 часов.

### 1.3. Проверить

```bash
ping bot.ваш-домен.uz
```

В ответе должен быть IP вашего сервера.

---

## Шаг 2. Nginx и SSL на сервере

### 2.1. Установить Nginx и Certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2.2. Создать конфиг Nginx для бота

Подставьте **свой домен** (например `bot.me-bobur.uz`). Порт приложения на хосте — **8001** (если у вас другой — измените в `proxy_pass`).

```bash
sudo nano /etc/nginx/sites-available/planning-bot
```

**Вариант A — сначала только HTTP (для выдачи сертификата):**

```nginx
server {
    listen 80;
    server_name bot.ваш-домен.uz;
    location / {
        return 200 'ok';
        add_header Content-Type text/plain;
    }
}
```

Сохраните (Ctrl+O, Enter, Ctrl+X).

```bash
sudo ln -sf /etc/nginx/sites-available/planning-bot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 2.3. Получить SSL-сертификат (Let's Encrypt)

```bash
sudo certbot --nginx -d bot.ваш-домен.uz
```

Укажите email, согласитесь с условиями. Certbot сам настроит HTTPS.

### 2.4. Прописать проксирование на приложение

Откройте конфиг снова и замените содержимое на полный вариант (порт **8001** — если приложение слушает другой, поменяйте):

```bash
sudo nano /etc/nginx/sites-available/planning-bot
```

```nginx
server {
    listen 80;
    server_name bot.ваш-домен.uz;
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name bot.ваш-домен.uz;

    ssl_certificate     /etc/letsencrypt/live/bot.ваш-домен.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.ваш-домен.uz/privkey.pem;

    location /webhook {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }

    location /webhook/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
    }
}
```

**Важно:** замените все вхождения `bot.ваш-домен.uz` на ваш реальный домен (например `bot.me-bobur.uz`). Если приложение слушает не 8001, измените `127.0.0.1:8001` на нужный порт.

Проверка и перезагрузка Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 2.5. Проверить с сервера

```bash
curl -s https://bot.ваш-домен.uz/health
```

Ожидается: `{"status":"ok"}`.

---

## Шаг 3. Переменные окружения и webhook

### 3.1. В `.env` на сервере

В каталоге проекта (например `/opt/bot`):

```bash
nano /opt/bot/.env
```

Укажите:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
WEBHOOK_BASE_URL=https://bot.ваш-домен.uz
```

Остальные переменные (`DATABASE_URL`, `REDIS_URL` и т.д.) оставьте как есть. Сохраните файл.

### 3.2. Установить webhook в Telegram

Подставьте **токен бота** и **ваш домен**:

```bash
curl -X POST "https://api.telegram.org/botВАШ_ТОКЕН/setWebhook?url=https://bot.ваш-домен.uz/webhook"
```

Успешный ответ: `{"ok":true,"result":true,...}`.

### 3.3. Перезапустить приложение (чтобы подхватить .env)

```bash
cd /opt/bot
docker compose restart app
```

### 3.4. Проверить

- Напишите боту в Telegram (например /start) — должен ответить.
- Проверка webhook:  
  `curl -s "https://api.telegram.org/botВАШ_ТОКЕН/getWebhookInfo"`  
  В ответе должно быть `"url":"https://bot.ваш-домен.uz/webhook"`.

---

## Краткая шпаргалка (подставьте свои значения)

| Действие | Команда / значение |
|----------|--------------------|
| Домен для бота | `bot.me-bobur.uz` (или ваш) |
| DNS | A-запись: `bot` → IP сервера |
| Порт приложения на хосте | `8001` (в Nginx: `proxy_pass http://127.0.0.1:8001`) |
| WEBHOOK_BASE_URL в .env | `https://bot.me-bobur.uz` |
| setWebhook | `https://api.telegram.org/bot<ТОКЕН>/setWebhook?url=https://bot.me-bobur.uz/webhook` |

---

## Автообновление SSL

Certbot настраивает таймер сам. Проверка:

```bash
sudo certbot renew --dry-run
```

---

## Если на одном сервере несколько сайтов

Один и тот же Nginx обслуживает много `server { ... }` блоков. Просто добавьте новый файл в `sites-available` (как выше) и включите его через `sites-enabled`. Порты 80 и 443 общие; различаются по `server_name` (домену).

После настройки домен будет указывать на ваш сервер, трафик к боту — через Nginx по HTTPS, webhook Telegram — на `https://ваш-домен/webhook`.
