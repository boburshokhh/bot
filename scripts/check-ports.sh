#!/usr/bin/env bash
# Проверка занятых портов на сервере и подсказки по свободным портам для бота.
# Запуск на целевом Ubuntu-сервере перед деплоем: bash scripts/check-ports.sh

set -e

echo "=== Слушающие TCP-порты на этом сервере ==="
if command -v ss &>/dev/null; then
  ss -tlnp 2>/dev/null || ss -tln
else
  netstat -tlnp 2>/dev/null || netstat -tln
fi

echo ""
echo "=== Порты, которые может использовать бот ==="
echo "  Приложение:     8000 или 8001  (выберите тот, которого нет в списке выше)"
echo "  PostgreSQL:     5432 или 5433  (только standalone)"
echo "  Redis:          6379 или 6380  (только standalone)"
echo "  Nginx (HTTP):   80             (обычно общий с другими сайтами)"
echo "  Nginx (HTTPS):  443            (обычно общий с другими сайтами)"
echo ""
echo "Если порт есть в списке выше — он ЗАНЯТ. В docker-compose укажите другой."
echo "Пример: если 8000 занят — приложение: 8001:8000; если 6379 занят — Redis: 6380:6379."
