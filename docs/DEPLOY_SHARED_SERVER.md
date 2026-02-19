# Deploy on shared Ubuntu server (multiple projects)

Step-by-step guide to deploy the Planning Bot on an Ubuntu server where **other projects already run**. You will check ports first, then deploy without conflicts. The server has a **public IP** and a **domain** for the webhook.

---

## What you need

- SSH access to the Ubuntu server
- A domain (e.g. `bot.yourdomain.com`) with an **A record** pointing to the server IP
- Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Step 1 — Check which ports are free

On the server, run:

```bash
# Quick list of all listening TCP ports
ss -tlnp
```

Or use the project script (from the repo root on the server):

```bash
cd /opt/bot   # or wherever you will clone the project
bash scripts/check-ports.sh
```

**Ports this bot uses:**

| Service    | Default host port | If busy, use   |
|-----------|--------------------|----------------|
| App (HTTP)| 8000 or 8001       | Other free port, e.g. 8002 |
| PostgreSQL| 5432 or 5433       | 5434, 5435… (standalone only) |
| Redis     | 6379 or 6380       | 6381, 6382… (standalone only) |
| Nginx     | 80, 443            | Usually **shared** with other sites (new server block) |

**Rule:** If a port appears in `ss -tlnp`, it is **occupied**. In `docker-compose.yml` use a **different host port** (left side of `"HOST:CONTAINER"`). Inside containers we keep 5432, 6379, 8000 unchanged.

---

## Step 2 — Choose deployment type

- **Standalone:** This server runs bot + its own PostgreSQL + Redis. Use `docker-compose.yml`. Adjust host ports in it if needed (see Step 4).
- **Shared DB:** PostgreSQL and Redis are on another server. Use `docker-compose.remote.yml` and set `DATABASE_URL` and `REDIS_URL` in `.env` to that server. Only the **app port** (e.g. 8000 or 8001) is used on this host.

---

## Step 3 — Clone project and prepare `.env`

```bash
sudo mkdir -p /opt/bot
sudo chown $USER:$USER /opt/bot
cd /opt/bot
git clone <YOUR_REPO_URL> .
```

```bash
cp .env.example .env
nano .env
```

**Standalone** — example `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
WEBHOOK_SECRET=your_random_secret_string
WEBHOOK_BASE_URL=https://bot.yourdomain.com

DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/planning_bot
REDIS_URL=redis://redis:6379/0

LOG_LEVEL=INFO
```

**Shared DB** — set `DATABASE_URL` and `REDIS_URL` to the **other server** (IP/host and port). Same `TELEGRAM_BOT_TOKEN`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`.

Use strong passwords; for standalone they must match `docker-compose.yml` (or set via env there).

---

## Step 4 — Set host ports in Docker (avoid conflicts)

If Step 1 showed that 8000, 5432, or 6379 are in use, edit the compose file you use.

**Standalone** — edit `docker-compose.yml`:

```yaml
# Example: app on host 8002, Postgres on 5434, Redis on 6381
services:
  postgres:
    ports:
      - "5434:5432"    # host:container
  redis:
    ports:
      - "6381:6379"
  app:
    ports:
      - "8002:8000"    # Nginx will proxy to 127.0.0.1:8002
```

**Shared DB** — edit `docker-compose.remote.yml` only if the app port must change:

```yaml
services:
  app:
    ports:
      - "8002:8000"    # if 8000 is busy
```

Remember the **host port** you chose for the app (e.g. 8002). You will use it in Nginx as `proxy_pass http://127.0.0.1:8002`.

---

## Step 5 — Start the bot

**Standalone:**

```bash
cd /opt/bot
docker compose up -d --build
```

**Shared DB:**

```bash
cd /opt/bot
docker compose -f docker-compose.remote.yml up -d --build
```

Run migrations once (standalone or from any host that can reach the DB):

```bash
docker compose exec app alembic upgrade head
```

Check:

```bash
docker compose ps
curl -s http://127.0.0.1:APP_PORT/health
```

Replace `APP_PORT` with the host port you set (e.g. 8000 or 8002). Expected: `{"status":"ok"}`.

---

## Step 6 — Nginx + HTTPS (shared 80/443)

Other sites can keep using the same Nginx on 80/443. Add a **new server block** for the bot.

Install Nginx and Certbot if not already:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create config (replace `bot.yourdomain.com` and `APP_PORT`):

```bash
sudo nano /etc/nginx/sites-available/planning-bot
```

Content (use your real app port, e.g. 8002):

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

Replace **APP_PORT** with your app’s host port (e.g. 8002).

Get SSL certificate:

```bash
sudo ln -sf /etc/nginx/sites-available/planning-bot /etc/nginx/sites-enabled/
# If first time: use a minimal server { listen 80; server_name bot.yourdomain.com; ... } then:
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d bot.yourdomain.com
```

If Certbot added its own SSL block, edit the file again to add the `location /webhook` and `location /health` blocks and set `proxy_pass http://127.0.0.1:APP_PORT;`. Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## Step 7 — Set Telegram webhook

Use your bot token and domain:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://bot.yourdomain.com/webhook"
```

With secret token (recommended):

```bash
SECRET=$(openssl rand -hex 32)
echo $SECRET
# Add WEBHOOK_SECRET=$SECRET to /opt/bot/.env

curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://bot.yourdomain.com/webhook\", \"secret_token\": \"$SECRET\"}"
```

Check:

```bash
curl -s https://bot.yourdomain.com/health
curl -s "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## Summary checklist

- [ ] Ran `ss -tlnp` (or `scripts/check-ports.sh`) and noted occupied ports
- [ ] Chose free host ports for app (and Postgres/Redis if standalone)
- [ ] Cloned repo, created `.env` with token, webhook URL, DB/Redis URLs
- [ ] Updated `docker-compose.yml` or `docker-compose.remote.yml` with chosen host ports
- [ ] Started stack, ran `alembic upgrade head`, checked `/health` on app port
- [ ] Added Nginx server block for `bot.yourdomain.com`, `proxy_pass` to correct app port
- [ ] Got SSL with Certbot, reloaded Nginx
- [ ] Set webhook with `setWebhook`, verified with `getWebhookInfo` and by messaging the bot

---

## Troubleshooting

| Problem | Check |
|--------|--------|
| Port already in use | `ss -tlnp`; change host port in compose and in Nginx `proxy_pass`. |
| 502 Bad Gateway | App container running; `proxy_pass` port matches app host port; `curl http://127.0.0.1:APP_PORT/health` works. |
| Webhook not received | HTTPS URL in `getWebhookInfo`; Nginx proxies `/webhook` to app; firewall allows 80/443. |

For more detail (firewall, logs, Celery) see [DEPLOYMENT_UBUNTU_WEBHOOK.md](DEPLOYMENT_UBUNTU_WEBHOOK.md).
