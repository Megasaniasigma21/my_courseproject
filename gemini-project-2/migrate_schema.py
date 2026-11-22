#!/usr/bin/env python3
"""
Скрипт безопасной миграции и рефакторинга базы данных Bochflix (SQLite).

Выполняет:
1. Создание резервной копии базы данных (data/cinema.db.backup_<timestamp>);
2. Приведение таблицы movies к целевой структуре колонок:
   - id, pnr, title, description, duration, quality, poster_url,
   - banner, mobile_poster, movie_page_url, logo_url, trailer,
   - is_hero_banner, is_new_and_popular, category_ids;
3. Нормализацию длительности (duration: '144' -> '2 ч 24 мин') и качества ('720p' -> '720p HD');
4. Автоматическое извлечение метаданных из реальных видеофайлов при их наличии;
5. Очистку дубликатов категорий и ремаппинг ID в фильмах;
6. Проверку целостности базы данных (PRAGMA integrity_check).
"""

import os
import sys
import shutil
import sqlite3
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from backend.utils.video_meta import (
        extract_video_metadata,
        normalize_duration_str,
        normalize_quality_str,
    )
    from backend.utils.category_parser import parse_category_ids, format_category_ids, is_popular_category
    from backend.utils.pnr import is_valid_pnr, generate_pnr
except ImportError:
    from backend.utils.video_meta import (
        extract_video_metadata,
        normalize_duration_str,
        normalize_quality_str,
    )
    from backend.utils.category_parser import parse_category_ids, format_category_ids, is_popular_category
    from backend.utils.pnr import is_valid_pnr, generate_pnr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")


def get_db_path() -> Path:
    """Возвращает путь к файлу БД."""
    return BASE_DIR / "data" / "cinema.db"


def backup_database(db_path: Path) -> Path:
    """Создает безопасную резервную копию базы данных."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.name}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    logger.info(f"Создан бэкап базы данных: {backup_path}")
    return backup_path


def run_migration(db_path: Optional[Path] = None) -> bool:
    """
    Основная процедура миграции и рефакторинга схемы БД.
    """
    if db_path is None:
        db_path = get_db_path()

    if not db_path.exists():
        logger.error(f"Файл базы данных не найден: {db_path}")
        return False

    logger.info(f"Начало миграции базы данных: {db_path}")
    backup_database(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # ----------------------------------------------------------------------
        # 1. Проверяем и удаляем лишние M2M таблицы (строго 2 таблицы)
        # ----------------------------------------------------------------------
        cursor.execute("DROP TABLE IF EXISTS movie_categories")
        conn.commit()
        logger.info("Удалена таблица movie_categories (если существовала).")

        # ----------------------------------------------------------------------
        # 2. Нормализация таблицы categories
        # ----------------------------------------------------------------------
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
        if cursor.fetchone():
            # Проверяем колонку icon_path
            cursor.execute("PRAGMA table_info(categories)")
            cat_cols = {col["name"]: col for col in cursor.fetchall()}
            if "icon_path" not in cat_cols:
                cursor.execute("ALTER TABLE categories ADD COLUMN icon_path VARCHAR(500)")
                conn.commit()

            if "icon_url" in cat_cols:
                cursor.execute("UPDATE categories SET icon_path = icon_url WHERE icon_path IS NULL AND icon_url IS NOT NULL")
                conn.commit()

            # Удаляем системную псевдо-категорию "Новое и популярное"
            cursor.execute("DELETE FROM categories WHERE LOWER(name) LIKE '%новое%' OR slug LIKE '%popular%'")
            conn.commit()

            # Дедупликация категорий по LOWER(TRIM(name))
            cursor.execute("SELECT id, name, slug, icon_path FROM categories ORDER BY id ASC")
            all_cats = cursor.fetchall()
            seen_names: Dict[str, int] = {}
            id_remapping: Dict[int, int] = {}

            for cat in all_cats:
                c_id = cat["id"]
                norm_name = cat["name"].strip().lower()
                if norm_name not in seen_names:
                    seen_names[norm_name] = c_id
                else:
                    canonical_id = seen_names[norm_name]
                    id_remapping[c_id] = canonical_id
                    cursor.execute("DELETE FROM categories WHERE id = ?", (c_id,))
                    logger.info(f"Удален дубликат категории '{cat['name']}' (ID {c_id} -> канонический ID {canonical_id})")

            conn.commit()
        else:
            id_remapping = {}

        # ----------------------------------------------------------------------
        # 3. Миграция таблицы movies
        # ----------------------------------------------------------------------
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='movies'")
        has_movies = cursor.fetchone() is not None

        old_movies = []
        if has_movies:
            cursor.execute("SELECT * FROM movies")
            old_movies = cursor.fetchall()
            logger.info(f"Найдено существующих записей фильмов: {len(old_movies)}")

        # Создаем временную таблицу с целевой схемой колонок
        cursor.execute("DROP TABLE IF EXISTS movies_new")
        cursor.execute("""
            CREATE TABLE movies_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pnr VARCHAR(6) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                duration VARCHAR(50) NOT NULL,
                quality VARCHAR(50) NOT NULL,
                poster_url VARCHAR(500) NOT NULL,
                banner VARCHAR(500) NOT NULL,
                mobile_poster VARCHAR(500) NOT NULL,
                movie_page_url VARCHAR(500) NOT NULL,
                logo_url VARCHAR(500) DEFAULT NULL,
                trailer VARCHAR(500) DEFAULT NULL,
                is_hero_banner BOOLEAN NOT NULL DEFAULT 0,
                is_new_and_popular BOOLEAN NOT NULL DEFAULT 0,
                category_ids VARCHAR(255) NOT NULL DEFAULT '',
                banner_desktop_url VARCHAR(500),
                banner_mobile_url VARCHAR(500),
                trailer_url VARCHAR(500),
                is_new_popular BOOLEAN NOT NULL DEFAULT 0,
                is_popular BOOLEAN NOT NULL DEFAULT 0,
                is_new BOOLEAN NOT NULL DEFAULT 0,
                rating FLOAT DEFAULT NULL
            )
        """)
        conn.commit()

        # Трансформация и перенос каждой записи
        video_dir = BASE_DIR / "media" / "video"
        for row in old_movies:
            r = dict(row)
            m_id = r.get("id")
            pnr = (r.get("pnr") or "").strip().upper()
            if not pnr or not is_valid_pnr(pnr):
                pnr = generate_pnr(6)

            title = (r.get("title") or "Без названия").strip()
            description = (r.get("description") or "Описание отсутствует").strip()

            # Длительность и качество
            duration_raw = r.get("duration")
            quality_raw = r.get("quality")

            # Проверяем, существует ли реальный видеофайл на диске
            video_file = video_dir / f"{pnr}.mp4"
            if video_file.is_file():
                meta = extract_video_metadata(video_file)
                duration = meta["duration_formatted"]
                quality = meta["quality_label"]
                logger.info(f"Фильм '{title}' [{pnr}]: метаданные извлечены из файла ({meta['backend']}): {quality}, {duration}")
            else:
                duration = normalize_duration_str(duration_raw)
                quality = normalize_quality_str(quality_raw)
                logger.info(f"Фильм '{title}' [{pnr}]: нормализованы значения: {duration_raw} -> {duration}, {quality_raw} -> {quality}")

            poster_url = r.get("poster_url") or "/images/error_items/error_items-img/bochflix-test-img-2.jpg"

            # Баннеры
            desktop_banner = (
                r.get("banner")
                or r.get("banner_desktop_url")
                or "/images/error_items/error_items-img/bochflix-test-img.png"
            )
            mobile_poster = (
                r.get("mobile_poster")
                or r.get("banner_mobile_url")
                or "/images/error_items/error_items-img/bochflix-test-img-3.jpg"
            )

            movie_page_url = r.get("movie_page_url") or f"/movie/video/{pnr}.mp4"
            logo_url = r.get("logo_url") or None
            trailer = r.get("trailer") or r.get("trailer_url") or None

            # Булевы флаги с безопасными дефолтами (false = 0)
            is_hero_banner = 1 if r.get("is_hero_banner") in (1, True, "1", "true") else 0
            is_new_and_popular = 1 if (
                r.get("is_new_and_popular") in (1, True, "1", "true")
                or r.get("is_new_popular") in (1, True, "1", "true")
                or r.get("is_popular") in (1, True, "1", "true")
            ) else 0

            is_new = 1 if r.get("is_new") in (1, True, "1", "true") else 0
            rating = r.get("rating")
            if rating is not None:
                try:
                    rating = float(rating)
                except (ValueError, TypeError):
                    rating = None

            # Привязка категорий
            cat_ids_raw = r.get("category_ids") or r.get("categories") or ""
            raw_ids = parse_category_ids(cat_ids_raw)
            # Применяем ремаппинг ID, если дубликаты категорий были объединены
            remapped_ids = [id_remapping.get(cid, cid) for cid in raw_ids]
            # Убираем дубликаты
            clean_category_ids_str = format_category_ids(remapped_ids)

            # Если для фильма ID 4 или 5 категории не были заданы — наполняем дефолтами
            if not clean_category_ids_str:
                if m_id == 4:
                    clean_category_ids_str = "1,4,6"
                elif m_id == 5:
                    clean_category_ids_str = "1,4,5"
                elif m_id == 6:
                    clean_category_ids_str = "4"

            cursor.execute("""
                INSERT INTO movies_new (
                    id, pnr, title, description, duration, quality, poster_url,
                    banner, mobile_poster, movie_page_url, logo_url, trailer,
                    is_hero_banner, is_new_and_popular, category_ids,
                    banner_desktop_url, banner_mobile_url, trailer_url,
                    is_new_popular, is_popular, is_new, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m_id, pnr, title, description, duration, quality, poster_url,
                desktop_banner, mobile_poster, movie_page_url, logo_url, trailer,
                is_hero_banner, is_new_and_popular, clean_category_ids_str,
                desktop_banner, mobile_poster, trailer,
                is_new_and_popular, is_new_and_popular, is_new, rating
            ))

        conn.commit()

        # Подменяем старую таблицу новой
        cursor.execute("DROP TABLE IF EXISTS movies")
        cursor.execute("ALTER TABLE movies_new RENAME TO movies")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_movies_pnr ON movies (pnr)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_movies_id ON movies (id)")
        conn.commit()

        # ----------------------------------------------------------------------
        # 4. Проверка целостности БД
        # ----------------------------------------------------------------------
        cursor.execute("PRAGMA integrity_check")
        check_result = cursor.fetchone()
        logger.info(f"Проверка целостности SQLite: {check_result[0]}")

        # Вывод итоговой структуры и записей
        cursor.execute("PRAGMA table_info(movies)")
        cols = cursor.fetchall()
        logger.info("Итоговая структура колонок таблицы movies:")
        for c in cols:
            logger.info(f"  - {c['name']} ({c['type']})")

        cursor.execute("SELECT id, pnr, title, duration, quality, banner, mobile_poster, is_new_and_popular, category_ids FROM movies")
        migrated_rows = cursor.fetchall()
        logger.info(f"Успешно мигрировано записей: {len(migrated_rows)}")
        for mr in migrated_rows:
            logger.info(f"  [ID {mr['id']}] {mr['pnr']} | {mr['title']} | {mr['duration']} | {mr['quality']} | cat_ids: {mr['category_ids']} | is_new_pop: {mr['is_new_and_popular']}")

        conn.close()
        logger.info("Миграция базы данных успешно завершена!")
        return True

    except Exception as exc:
        conn.rollback()
        conn.close()
        logger.error(f"Ошибка при выполнении миграции: {exc}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
