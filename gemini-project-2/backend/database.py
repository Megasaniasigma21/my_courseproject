"""SQLite: каталог, зашифрованные профили и серверные сессии."""

import sys
import logging
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session

BASE_DIR_PATH = Path(__file__).resolve().parent.parent
if str(BASE_DIR_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PATH))

try:
    from .config import settings
    from .models import Base, Category, Movie
    from .utils.category_parser import parse_category_ids
    from .utils.video_meta import normalize_duration_str, normalize_quality_str
except ImportError:
    from backend.config import settings
    from backend.models import Base, Category, Movie
    from backend.utils.category_parser import parse_category_ids
    from backend.utils.video_meta import normalize_duration_str, normalize_quality_str

logger = logging.getLogger("bochflix.database")

# Настройка движка SQLite
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовые категории каталога (без 'Новое и популярное', т.к. это отдельный флаг is_new_and_popular)
DEFAULT_CATEGORIES = [
    {"id": 1, "name": "Фильмы", "slug": "movies", "icon_path": None},
    {"id": 2, "name": "Сериалы", "slug": "series", "icon_path": None},
    {"id": 3, "name": "Мультфильмы", "slug": "cartoons", "icon_path": None},
    {"id": 4, "name": "Боевики", "slug": "action", "icon_path": None},
    {"id": 5, "name": "Фантастика", "slug": "sci-fi", "icon_path": None},
    {"id": 6, "name": "Драмы", "slug": "drama", "icon_path": None},
    {"id": 7, "name": "Груз 200", "slug": "comedy", "icon_path": None},
]


def run_migrations() -> None:
    """
    Миграция схемы каталога; таблицы пользователей и сессий создаются из моделей:
    1. Удаляет промежуточную таблицу movie_categories, если она была создана ранее.
    2. Создает/обновляет таблицы movies и categories.
    3. Добавляет целевые колонки в movies: banner, mobile_poster, trailer, is_new_and_popular, category_ids.
    4. Синхронизирует данные между старыми и новыми колонками.
    5. Нормализует категории без дубликатов.
    """
    with engine.connect() as conn:
        # Обратная совместимость со старой схемой каталога
        conn.execute(text("DROP TABLE IF EXISTS movie_categories"))
        conn.commit()

    # Создаём все таблицы моделей, если их ещё нет
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.connect() as conn:
        # 3. Обновляем таблицу categories
        if "categories" in existing_tables:
            cat_cols = [col["name"] for col in inspector.get_columns("categories")]
            if "icon_path" not in cat_cols:
                conn.execute(text("ALTER TABLE categories ADD COLUMN icon_path VARCHAR(500)"))
                conn.commit()
            if "icon_url" in cat_cols:
                conn.execute(text("UPDATE categories SET icon_path = icon_url WHERE icon_path IS NULL AND icon_url IS NOT NULL"))
                conn.commit()

            # Удаляем системную псевдо-категорию "Новое и популярное" (она хранится флагом в movies)
            conn.execute(text("DELETE FROM categories WHERE LOWER(name) LIKE '%новое%' OR slug LIKE '%popular%'"))
            conn.commit()

        # 4. Обновляем таблицу movies
        if "movies" in existing_tables:
            mov_cols = [col["name"] for col in inspector.get_columns("movies")]

            for name, column_type in (("year", "INTEGER"), ("genre", "VARCHAR(255)"),
                                      ("creator", "VARCHAR(255)"), ("license", "VARCHAR(255)"),
                                      ("source_url", "VARCHAR(500)")):
                if name not in mov_cols:
                    conn.execute(text(f"ALTER TABLE movies ADD COLUMN {name} {column_type}"))
            conn.commit()

            # Целевые колонки
            if "banner" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN banner VARCHAR(500)"))
                conn.commit()
            if "mobile_poster" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN mobile_poster VARCHAR(500)"))
                conn.commit()
            if "trailer" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN trailer VARCHAR(500)"))
                conn.commit()
            if "is_new_and_popular" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN is_new_and_popular BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
            if "category_ids" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN category_ids VARCHAR(255)"))
                conn.commit()

            # Совместимые колонки
            if "banner_desktop_url" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN banner_desktop_url VARCHAR(500)"))
                conn.commit()
            if "banner_mobile_url" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN banner_mobile_url VARCHAR(500)"))
                conn.commit()
            if "trailer_url" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN trailer_url VARCHAR(500)"))
                conn.commit()
            if "is_new_popular" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN is_new_popular BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
            if "is_hero_banner" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN is_hero_banner BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
            if "is_new" not in mov_cols:
                conn.execute(text("ALTER TABLE movies ADD COLUMN is_new BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()

            # Синхронизация данных в обе стороны
            conn.execute(text("""
                UPDATE movies SET 
                    banner = COALESCE(banner, banner_desktop_url),
                    banner_desktop_url = COALESCE(banner_desktop_url, banner),
                    mobile_poster = COALESCE(mobile_poster, banner_mobile_url),
                    banner_mobile_url = COALESCE(banner_mobile_url, mobile_poster),
                    trailer = COALESCE(trailer, trailer_url),
                    trailer_url = COALESCE(trailer_url, trailer)
            """))

            # Синхронизация флагов популярности
            conn.execute(text("""
                UPDATE movies SET
                    is_new_and_popular = CASE WHEN is_new_and_popular = 1 OR is_new_popular = 1 OR is_popular = 1 THEN 1 ELSE 0 END,
                    is_new_popular = CASE WHEN is_new_and_popular = 1 OR is_new_popular = 1 OR is_popular = 1 THEN 1 ELSE 0 END
            """))
            conn.commit()


def seed_default_data() -> None:
    """
    Наполняет БД базовыми категориями (ID 1-7).
    """
    db = SessionLocal()
    try:
        for cat_data in DEFAULT_CATEGORIES:
            exists = db.query(Category).filter(Category.id == cat_data["id"]).first()
            if not exists:
                new_cat = Category(
                    id=cat_data["id"],
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    icon_path=cat_data["icon_path"],
                )
                db.add(new_cat)
            else:
                exists.name = cat_data["name"]
                exists.slug = cat_data["slug"]
                if cat_data["icon_path"] and not exists.icon_path:
                    exists.icon_path = cat_data["icon_path"]
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    """Полная инициализация БД."""
    run_migrations()
    seed_default_data()


def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency для получения сессии базы данных."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
