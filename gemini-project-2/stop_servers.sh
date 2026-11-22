#!/usr/bin/env bash
# ==============================================================================
# Скрипт остановки всех серверов Bochflix (Nginx + FastAPI)
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "=========================================="
echo "🛑 Остановка всех серверов Bochflix..."
echo "=========================================="

# 1. Остановка Nginx
echo "[1/2] Остановка Nginx..."
if [ -x "/opt/homebrew/bin/nginx" ]; then
    /opt/homebrew/bin/nginx -s stop 2>/dev/null
fi
pkill -f "nginx" 2>/dev/null

# 2. Остановка FastAPI (uvicorn / run_server.py)
echo "[2/2] Остановка FastAPI бэкенда..."
pkill -f "run_server.py" 2>/dev/null
pkill -f "uvicorn" 2>/dev/null

# 3. Принудительное освобождение портов 8000 и 8080, если процессы зависли
PIDS_8000=$(lsof -ti :8000 2>/dev/null)
if [ -n "$PIDS_8000" ]; then
    echo "  -> Принудительное освобождение порта 8000 (PID: $PIDS_8000)..."
    kill -9 $PIDS_8000 2>/dev/null
fi

PIDS_8080=$(lsof -ti :8080 2>/dev/null)
if [ -n "$PIDS_8080" ]; then
    echo "  -> Принудительное освобождение порта 8080 (PID: $PIDS_8080)..."
    kill -9 $PIDS_8080 2>/dev/null
fi

sleep 1

# Проверка результата
REMAINING_8000=$(lsof -ti :8000 2>/dev/null)
REMAINING_8080=$(lsof -ti :8080 2>/dev/null)

if [ -z "$REMAINING_8000" ] && [ -z "$REMAINING_8080" ]; then
    echo "✅ Все сервисы успешно остановлены!"
    echo "   • FastAPI (порт 8000): свободен"
    echo "   • Nginx   (порт 8080): свободен"
else
    echo "⚠️ Внимание, некоторые порты все еще заняты:"
    [ -n "$REMAINING_8000" ] && echo "   • Порт 8000 занят PID: $REMAINING_8000"
    [ -n "$REMAINING_8080" ] && echo "   • Порт 8080 занят PID: $REMAINING_8080"
fi
echo "=========================================="
