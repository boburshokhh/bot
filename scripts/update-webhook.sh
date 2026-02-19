#!/usr/bin/env bash
# После перезапуска ngrok URL меняется. Скрипт получает новый URL и обновляет webhook в Telegram.
# Запуск: ./scripts/update-webhook.sh   или  sudo /opt/bot/scripts/update-webhook.sh
# Использование: нужен /opt/bot/.env с TELEGRAM_BOT_TOKEN (или задайте TELEGRAM_BOT_TOKEN в окружении).

set -e

BOT_DIR="${BOT_DIR:-/opt/bot}"
NGROK_API="${NGROK_API:-http://127.0.0.1:4040}"
MAX_WAIT="${MAX_WAIT:-60}"

if [ -f "$BOT_DIR/.env" ]; then
  TELEGRAM_BOT_TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' "$BOT_DIR/.env" | cut -d= -f2- | tr -d '\r')
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN not set. Set in $BOT_DIR/.env or environment." >&2
  exit 1
fi

echo "Waiting for ngrok API at $NGROK_API (max ${MAX_WAIT}s)..."
for i in $(seq 1 "$MAX_WAIT"); do
  JSON=$(curl -s "$NGROK_API/api/tunnels" 2>/dev/null || true)
  URL=$(echo "$JSON" | grep -o '"public_url":"https://[^"]*"' | head -1 | sed 's/"public_url":"//;s/"$//')
  if [ -n "$URL" ]; then
    break
  fi
  sleep 1
done

if [ -z "$URL" ]; then
  echo "ERROR: ngrok tunnel not found. Is ngrok running? Check: systemctl status ngrok" >&2
  exit 1
fi

WEBHOOK_URL="${URL}/webhook"
echo "Setting webhook to: $WEBHOOK_URL"
RESP=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")
if echo "$RESP" | grep -q '"ok":true'; then
  echo "Webhook updated successfully."
else
  echo "ERROR: $RESP" >&2
  exit 1
fi
