#!/usr/bin/env bash
# ==============================================================================
# Скрипт запуска серверов Bochflix (Nginx + FastAPI)
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

BACKGROUND=false
if [ "$1" = "-d" ] || [ "$1" = "--daemon" ] || [ "$1" = "-b" ] || [ "$1" = "--background" ]; then
    BACKGROUND=true
fi

echo "=========================================="
echo "🚀 Запуск серверов Bochflix..."
echo "=========================================="

# 1. Предварительная очистка зависших процессов, если порты заняты
OLD_8000=$(lsof -ti :8000 2>/dev/null)
OLD_8080=$(lsof -ti :8080 2>/dev/null)

if [ -n "$OLD_8000" ] || [ -n "$OLD_8080" ]; then
    echo "[*] Обнаружены старые процессы. Очищаем перед запуском..."
    ./stop_servers.sh > /dev/null 2>&1
    sleep 1
fi

# 2. Запуск Nginx
echo "[1/2] Запуск веб-сервера Nginx..."
if [ -x "/opt/homebrew/bin/nginx" ]; then
    /opt/homebrew/bin/nginx
    NGINX_STATUS=$?
else
    nginx
    NGINX_STATUS=$?
fi

if [ $NGINX_STATUS -eq 0 ]; then
    echo "  [+] Nginx успешно запущен на порту 8080"
else
    echo "  [!] Ошибка при запуске Nginx (код: $NGINX_STATUS)"
fi

# Локальный IP адрес для вывода (Wi-Fi / Ethernet)
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")

echo ""
echo "[2/2] Запуск FastAPI бэкенда..."
echo "  [+] FastAPI бэкенд: http://127.0.0.1:8000"
echo "  [+] Swagger API:    http://127.0.0.1:8000/docs"
echo "  [+] Сайт (Nginx):   http://localhost:8080"
if [ "$LOCAL_IP" != "127.0.0.1" ]; then
    echo "  [+] Доступ с телефона в локальной сети: http://${LOCAL_IP}:8080"
fi
echo "=========================================="

if [ "$BACKGROUND" = true ]; then
    echo "[*] Запуск в фоновом режиме (демон)..."
    nohup .venv/bin/python run_server.py > uvicorn.log 2>&1 &
    FASTAPI_PID=$!
    echo $FASTAPI_PID > .fastapi.pid
    sleep 1
    echo "✅ Все сервисы запущены в фоне!"
    echo "   Для остановки используйте: ./stop_servers.sh"
    echo "   Для просмотра логов FastAPI: tail -f uvicorn.log"
    echo "=========================================="
    exit 0
fi

# Фоновый обработчик для корректной остановки Nginx при выходе по Ctrl+C
cleanup() {
    echo ""
    echo "=========================================="
    echo "🛑 Завершение работы. Останавливаем Nginx..."
    if [ -x "/opt/homebrew/bin/nginx" ]; then
        /opt/homebrew/bin/nginx -s stop 2>/dev/null
    fi
    pkill -f "nginx" 2>/dev/null
    echo "✅ Nginx остановлен. Порты освобождены."
    echo "=========================================="
    exit 0
}

trap cleanup INT TERM EXIT

echo "[*] FastAPI запущен на переднем плане. Для завершения нажмите Ctrl + C"
echo ""

# Запуск Python FastAPI на переднем плане
.venv/bin/python run_server.py
