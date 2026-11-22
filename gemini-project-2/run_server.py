#!/usr/bin/env python3
"""
Скрипт быстрого запуска FastAPI сервера Bochflix.
Использование:
    python run_server.py
"""

import sys
from pathlib import Path
import uvicorn

# Добавляем корень проекта в путь поиска модулей
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import settings

if __name__ == "__main__":
    print(f"[*] Запуск сервера {settings.APP_NAME}...")
    print(f"[*] Адрес: http://{settings.HOST}:{settings.PORT}")
    print(f"[*] Документация Swagger: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"[*] Для остановки нажмите Ctrl + C\n")
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
