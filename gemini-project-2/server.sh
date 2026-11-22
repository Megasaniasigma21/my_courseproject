#!/usr/bin/env bash
# ==============================================================================
# Универсальный скрипт управления серверами Bochflix
# Использование:
#   ./server.sh start       - Запустить Nginx и FastAPI (Ctrl+C остановит оба)
#   ./server.sh start -d    - Запустить в фоновом режиме (daemon)
#   ./server.sh stop        - Остановить Nginx и FastAPI
#   ./server.sh restart     - Перезапустить оба сервиса
#   ./server.sh status      - Проверить статус работы сервисов
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

COMMAND="$1"
shift

case "$COMMAND" in
    start)
        ./start_servers.sh "$@"
        ;;
    stop)
        ./stop_servers.sh
        ;;
    restart)
        ./restart_servers.sh "$@"
        ;;
    status)
        echo "=========================================="
        echo "📊 Статус серверов Bochflix"
        echo "=========================================="
        
        FASTAPI_PID=$(lsof -ti :8000 2>/dev/null)
        if [ -n "$FASTAPI_PID" ]; then
            echo "🟢 FastAPI (порт 8000): РАБОТАЕТ (PID: $FASTAPI_PID)"
        else
            echo "🔴 FastAPI (порт 8000): ОСТАНОВЛЕН"
        fi

        NGINX_PID=$(lsof -ti :8080 2>/dev/null)
        if [ -n "$NGINX_PID" ]; then
            echo "🟢 Nginx   (порт 8080): РАБОТАЕТ (PID: $NGINX_PID)"
        else
            echo "🔴 Nginx   (порт 8080): ОСТАНОВЛЕН"
        fi
        
        echo "------------------------------------------"
        if [ -n "$FASTAPI_PID" ] && [ -n "$NGINX_PID" ]; then
            echo "✅ Все сервисы активны и готовы к работе."
            echo "   Веб-сайт: http://localhost:8080"
            echo "   FastAPI:  http://127.0.0.1:8000"
        elif [ -z "$FASTAPI_PID" ] && [ -z "$NGINX_PID" ]; then
            echo "⚪ Серверы выключены."
        else
            echo "⚠️ Внимание: работает только часть сервисов!"
        fi
        echo "=========================================="
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status} [-d|--daemon]"
        echo ""
        echo "Команды:"
        echo "  ./server.sh start      - Запуск сервисов на переднем плане"
        echo "  ./server.sh start -d   - Фоновый запуск сервисов"
        echo "  ./server.sh stop       - Полная остановка всех сервисов"
        echo "  ./server.sh restart    - Перезапуск всех сервисов"
        echo "  ./server.sh status     - Проверка статуса (порты 8000 и 8080)"
        echo ""
        echo "Также доступны отдельные скрипты:"
        echo "  ./start.sh   / ./start_servers.sh"
        echo "  ./stop.sh    / ./stop_servers.sh"
        echo "  ./restart.sh / ./restart_servers.sh"
        exit 1
        ;;
esac
