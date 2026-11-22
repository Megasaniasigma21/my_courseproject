"""
Главная точка входа FastAPI приложения для кинохостинга.
Настраивает CORS, маршруты, статическую отдачу для режима разработки и инициализацию БД.
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Обеспечиваем корректный импорт при прямом запуске `python backend/main.py`
BASE_DIR_PATH = Path(__file__).resolve().parent.parent
if str(BASE_DIR_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PATH))

from fastapi import FastAPI
from backend.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

try:
    from .config import settings, BASE_DIR
    from .database import init_db
    from .routes.movies import router as movies_router
    from .routes.films import router as films_router
except ImportError:
    from backend.config import settings, BASE_DIR
    from backend.database import init_db
    from backend.routes.movies import router as movies_router
    from backend.routes.films import router as films_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: инициализация БД при старте."""
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Backend API для кинохостинга: каталоги, треки, промо-слайдеры.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Настройка CORS Middleware для беспрепятственных запросов с фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение маршрутов API (поддерживаем оба префикса: /api и /api/v1)
app.include_router(movies_router, prefix="/api")
app.include_router(movies_router, prefix="/api/v1")
app.include_router(films_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

# Раздача статики для режима разработки (постеры, баннеры, тестовые изображения)
# В продакшене отдачей статики занимается Nginx, но для автономной работы и тестирования
# с мобильными приложениями (Android) FastAPI умеет отдавать всё напрямую.
if settings.MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")

# Раздача видео по пути /movie/video/ для прямой работы без Nginx (Android ExoPlayer)
video_dir = settings.MEDIA_DIR / "video"
if video_dir.exists():
    app.mount("/movie/video", StaticFiles(directory=str(video_dir)), name="movie_video")

# Также монтируем папку IMAGES из фронтенда для удобства локального тестирования
frontend_images_dir = BASE_DIR / "front-end" / "IMAGES"
if frontend_images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(frontend_images_dir)), name="images")


@app.get("/", summary="Корневой статус API")
def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "endpoints": {
            "movies": "/api/v1/movies",
            "banners": "/api/v1/banners",
        },
    }


@app.get("/health", summary="Проверка работоспособности")
def health():
    return {"status": "ok"}


def run():
    """Запуск Uvicorn сервера."""
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    run()
