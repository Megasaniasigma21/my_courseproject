"""
Модуль настроек приложения (FastAPI, SQLite, CORS, пути).
Поддерживает переопределение через переменные окружения и .env файл.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Конфигурационные параметры кинохостинга."""

    APP_NAME: str = "Bochflix Cinema Backend API"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Сервер (0.0.0.0 позволяет слушать как localhost, так и локальную сеть Wi-Fi)
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Пути к БД и медиа
    DB_PATH: Path = BASE_DIR / "data" / "cinema.db"
    DATABASE_URL: str = ""
    MEDIA_DIR: Path = BASE_DIR / "media"

    # CORS: разрешаем обращение с фронтенда (включая локальные сервера и file://)
    CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5500",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5500",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "null",  # Для локальных файлов file:/// в браузере
        "*",
    ]

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        # Убедимся, что папка для базы данных существует
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH.resolve()}"

        # Убедимся, что папка медиа существует
        self.MEDIA_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
