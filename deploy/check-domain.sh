#!/bin/bash
# Диагностика доступа по домену integration-wa.ru
# Запуск на сервере: bash deploy/check-domain.sh

set -e
DOMAIN="${1:-integration-wa.ru}"
echo "=== Проверка доступа по домену $DOMAIN ==="
echo ""

echo "1. Фронт (порт 3000):"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:3000/ 2>/dev/null || echo "fail")
echo "   curl http://127.0.0.1:3000/ -> HTTP $CODE"
if [ "$CODE" != "200" ] && [ "$CODE" != "307" ]; then
  echo "   Ожидалось 200 или 307. Запустите: docker compose up -d frontend"
fi
echo ""

echo "2. Бэкенд (порт 8000):"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:8000/health 2>/dev/null || echo "fail")
echo "   curl http://127.0.0.1:8000/health -> HTTP $CODE"
echo ""

echo "3. Кто слушает порт 80:"
(sudo ss -tlnp 2>/dev/null | grep ':80 ') || (sudo netstat -tlnp 2>/dev/null | grep ':80 ') || echo "   Порт 80 не занят или нет прав"
echo ""

echo "4. Nginx (если установлен на хосте):"
if command -v nginx >/dev/null 2>&1; then
  sudo nginx -t 2>&1 || true
  echo "   Включённые сайты:"
  ls -la /etc/nginx/sites-enabled/ 2>/dev/null || true
else
  echo "   Nginx не установлен на хосте (можно использовать Nginx в Docker — см. README)"
fi
echo ""

echo "5. Запрос по домену (Host: $DOMAIN) на локальный 80:"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 -H "Host: $DOMAIN" http://127.0.0.1:80/ 2>/dev/null || echo "fail")
echo "   curl -H 'Host: $DOMAIN' http://127.0.0.1:80/ -> HTTP $CODE"
if [ "$CODE" = "200" ] || [ "$CODE" = "307" ]; then
  echo "   Локально по доменному имени отвечает. Проверьте DNS и фаервол."
else
  echo "   Локально не отвечает. Настройте Nginx (хостовый или docker compose с сервисом nginx)."
fi
echo ""

echo "6. DNS $DOMAIN:"
dig +short "$DOMAIN" 2>/dev/null || nslookup "$DOMAIN" 2>/dev/null || echo "   (dig/nslookup недоступны)"
echo ""

echo "7. Контейнеры:"
docker compose ps 2>/dev/null || docker-compose ps 2>/dev/null || echo "   docker compose не запущен из этой папки"
echo ""
echo "Готово. Если Nginx в Docker — поднимите: docker compose up -d nginx"
