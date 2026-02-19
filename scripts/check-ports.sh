#!/usr/bin/env bash
# Check which ports are in use on the server and suggest free ports for the bot.
# Run on the target Ubuntu server before deploy: bash scripts/check-ports.sh

set -e

echo "=== Listening TCP ports on this server ==="
if command -v ss &>/dev/null; then
  ss -tlnp 2>/dev/null || ss -tln
else
  netstat -tlnp 2>/dev/null || netstat -tln
fi

echo ""
echo "=== Ports this bot may use ==="
echo "  App (HTTP):     8000 or 8001  (choose one not in the list above)"
echo "  PostgreSQL:     5432 or 5433  (standalone only)"
echo "  Redis:          6379 or 6380 (standalone only)"
echo "  Nginx (HTTP):   80            (often shared with other sites)"
echo "  Nginx (HTTPS):  443           (often shared with other sites)"
echo ""
echo "If a port appears above, it is OCCUPIED — use a different one in docker-compose."
echo "Example: if 8000 is in use, map app to 8001:8000; if 6379 is in use, use 6380:6379 for Redis."
