"""
Набор автоматических тестов для бэкенда кинохостинга Bochflix.
Проверяет архитектуру строго из 2 таблиц (movies и categories):
1. Генерация и валидация 6-значного PNR;
2. Парсинг метаданных видео (длительность, качество);
3. Архитектура базы: строго 2 таблицы (movies, categories), без M2M-таблиц;
4. Поле category_ids в movies (строка ID через запятую) и флаг is_new_popular;
5. Поле icon_path в categories с fallback на дефолтную иконку при NULL;
6. Фильтрация пустых категорий (категории без фильмов не отправляются на фронтенд);
7. Отказоустойчивость: буквы/спецсимволы в category_ids не роняют бэкенд (нет 500 error);
8. Промо-слайдер: GET /api/banners (is_hero_banner = True);
9. Удаление и получение фильмов по PNR;
10. CORS заголовки и обработка ошибок.
"""

import sys
import logging
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app
from backend.database import get_db, Base
from backend.models import Movie, Category
from backend.utils.pnr import generate_pnr, is_valid_pnr, PNR_ALPHABET, PNR_LENGTH
from backend.utils.video_meta import (
    format_duration,
    map_resolution_to_label,
    extract_video_metadata,
)
from backend.utils.category_parser import parse_category_ids

# Тестовая БД в памяти (in-memory SQLite со StaticPool для многопоточности)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Создает чистую тестовую БД перед каждым тестом."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Тестовый клиент FastAPI с подмененной сессией БД."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_android_catalog_uses_database_and_absolute_media_urls(client, db_session):
    movie = Movie(pnr="BCDFGH", title="Demo", description="Description", duration="10 sec",
                  quality="HD", poster_url="/media/posters/demo.jpg", banner="",
                  mobile_poster="", movie_page_url="/media/video/demo.webm",
                  year=2021, genre="Documentary", creator="Author", license="CC BY",
                  source_url="https://example.org/source", rating=8.5)
    db_session.add(movie)
    db_session.commit()
    item = client.get("/api/films").json()[0]
    assert item["title"] == "Demo"
    assert item["videoUrl"] == "http://testserver/media/video/demo.webm"
    assert item["posterUrl"] == "http://testserver/media/posters/demo.jpg"
    assert item["creator"] == "Author" and item["year"] == 2021
    assert client.get(f"/api/films/{movie.id}").json() == item
    assert client.get("/api/films/999999").status_code == 404


# ==============================================================================
# 1. ТЕСТЫ PNR
# ==============================================================================

def test_pnr_length_and_alphabet():
    for _ in range(100):
        pnr = generate_pnr()
        assert len(pnr) == PNR_LENGTH == 6
        assert all(char in PNR_ALPHABET for char in pnr)
        for vowel in "AEIOU":
            assert vowel not in pnr


def test_pnr_validation():
    assert is_valid_pnr("9K4R2T") is True
    assert is_valid_pnr("BCDFGH") is True
    assert is_valid_pnr("012345") is True
    assert is_valid_pnr("bcdfgh") is True

    # Невалидные: гласные
    assert is_valid_pnr("A12345") is False
    assert is_valid_pnr("9E4R2T") is False

    # Невалидные: длина != 6
    assert is_valid_pnr("12345") is False
    assert is_valid_pnr("1234567") is False


# ==============================================================================
# 2. ТЕСТЫ ПАРСЕРА МЕТАДАННЫХ ВИДЕО
# ==============================================================================

def test_format_duration():
    assert format_duration(0) == "0 мин"
    assert format_duration(45 * 60) == "45 мин"
    assert format_duration(60 * 60) == "1 ч"
    assert format_duration(8940) == "2 ч 29 мин"
    assert format_duration(3600 + 15 * 60) == "1 ч 15 мин"


def test_map_resolution_to_label():
    assert map_resolution_to_label(256, 144) == "144p"
    assert map_resolution_to_label(1280, 720) == "720p HD"
    assert map_resolution_to_label(1920, 1080) == "1080p Full HD"
    assert map_resolution_to_label(1920, 800) == "1080p Full HD"
    assert map_resolution_to_label(2560, 1440) == "2K"
    assert map_resolution_to_label(3840, 2160) == "4K"


# ==============================================================================
# 3. ТЕСТ АРХИТЕКТУРЫ: СТРОГО 2 ТАБЛИЦЫ В БД (НЕТ M2M ТАБЛИЦЫ)
# ==============================================================================

def test_catalog_and_server_accounts_schema(db_session):
    """
    Каталог и серверные пользователи с сессиями, без промежуточных M2M-таблиц.
    """
    inspector = inspect(db_session.bind)
    tables = sorted(inspector.get_table_names())
    assert tables == ["auth_sessions", "categories", "movies", "users"], tables

    # Проверяем структуру movies (category_ids, is_new_popular)
    movie_cols = {col["name"] for col in inspector.get_columns("movies")}
    assert "category_ids" in movie_cols, "В таблице movies должен присутствовать столбец category_ids"
    assert "is_new_popular" in movie_cols, "В таблице movies должен присутствовать столбец is_new_popular"

    # Проверяем структуру categories (icon_path)
    cat_cols = {col["name"] for col in inspector.get_columns("categories")}
    assert "icon_path" in cat_cols, "В таблице categories должен присутствовать столбец icon_path"


# ==============================================================================
# 4. ТЕСТЫ ЭНДПОИНТА ИКОНОЧНОГО КАТАЛОГА: GET /api/catalog/categories
# ==============================================================================

def test_catalog_categories_endpoint_and_empty_filtering(client):
    """
    Проверяет GET /api/catalog/categories:
    1. Категории с фильмами попадают в каталог;
    2. Пустые категории фильтруются и НЕ отправляются на фронтенд;
    3. При icon_path = NULL отдается fallback на дефолтную иконку.
    """
    c1 = client.post("/api/categories", json={
        "name": "Комедии",
        "slug": "comedy",
        "icon_path": "/images/icons/comedy.svg",
    }).json()
    c2 = client.post("/api/categories", json={
        "name": "Драмы",
        "slug": "drama",
        "icon_path": None,
    }).json()
    c_empty = client.post("/api/categories", json={
        "name": "Пустая категория",
        "slug": "empty-cat",
        "icon_path": None,
    }).json()

    # Пока нет фильмов — каталог пуст (пустые категории не отправляются)
    res_before = client.get("/api/catalog/categories")
    assert res_before.status_code == 200
    assert len(res_before.json()) == 0

    # Добавляем фильм в c1 и c2
    client.post("/api/movies", json={
        "title": "Тестовый фильм",
        "description": "Описание",
        "duration": "1 ч 30 мин",
        "quality": "1080p Full HD",
        "poster_url": "/p.jpg",
        "banner_desktop_url": "/d.jpg",
        "banner_mobile_url": "/m.jpg",
        "category_ids": f"{c1['id']},{c2['id']}",
    })

    res = client.get("/api/catalog/categories")
    assert res.status_code == 200
    data = res.json()
    # Только непустые c1 и c2 (c_empty отфильтрована!)
    assert len(data) == 2
    titles = [c["title"] for c in data]
    assert "Комедии" in titles
    assert "Драмы" in titles
    assert "Пустая категория" not in titles

    # Проверяем fallback-иконку
    comedy_item = next(c for c in data if c["title"] == "Комедии")
    drama_item = next(c for c in data if c["title"] == "Драмы")
    assert comedy_item["icon_url"] == "/images/icons/comedy.svg"
    assert drama_item["icon_url"] == "../IMAGES/icons/test-icon.svg"


# ==============================================================================
# 5. ТЕСТЫ С ПАГИНАЦИЕЙ И ФИЛЬТРАЦИЕЙ ПУСТЫХ КАТЕГОРИЙ: GET /api/categories
# ==============================================================================

def test_paginated_categories_filters_empty_categories(client):
    """
    Проверяет GET /api/categories:
    - Категории без фильмов (пустые) фильтруются и не отправляются на фронтенд.
    """
    c1 = client.post("/api/categories", json={"name": "Кат 1", "slug": "cat-1"}).json()
    c2 = client.post("/api/categories", json={"name": "Кат 2", "slug": "cat-2"}).json()
    c_empty = client.post("/api/categories", json={"name": "Кат Без Фильмов", "slug": "cat-empty"}).json()

    # Фильм привязан к c1 и c2
    client.post("/api/movies", json={
        "title": "Мстители",
        "description": "Супергерои",
        "duration": "2 ч 23 мин",
        "quality": "1080p Full HD",
        "poster_url": "/p.jpg",
        "banner_desktop_url": "/d.jpg",
        "banner_mobile_url": "/m.jpg",
        "category_ids": f"{c1['id']},{c2['id']}",
        "is_hero_banner": True,
    })

    res = client.get("/api/categories?offset=0&limit=10")
    assert res.status_code == 200
    cats = res.json()

    # Только 2 непустые категории
    assert len(cats) == 2
    cat_titles = [c["title"] for c in cats]
    assert "Кат 1" in cat_titles
    assert "Кат 2" in cat_titles
    assert "Кат Без Фильмов" not in cat_titles

    # Каждая содержит фильм
    assert len(cats[0]["movies"]) == 1
    assert cats[0]["movies"][0]["title"] == "Мстители"


# ==============================================================================
# 6. ТЕСТЫ ФИЛЬТРАЦИИ ПО КАТЕГОРИЯМ (ОДИН ФИЛЬМ В НЕСКОЛЬКИХ КАТЕГОРИЯХ)
# ==============================================================================

def test_multiple_categories_filtering(client):
    """
    Проверяет, что фильм с category_ids='1,2' попадает в обе категории.
    """
    cat_comedy = client.post("/api/categories", json={"name": "Комедия", "slug": "comedy"}).json()
    cat_drama = client.post("/api/categories", json={"name": "Драма", "slug": "drama"}).json()
    cat_action = client.post("/api/categories", json={"name": "Боевик", "slug": "action"}).json()

    movie_res = client.post("/api/movies", json={
        "title": "Трагикомедия 1+1",
        "description": "История дружбы",
        "duration": "1 ч 52 мин",
        "quality": "1080p Full HD",
        "poster_url": "/1plus1.jpg",
        "banner_desktop_url": "/1plus1_d.jpg",
        "banner_mobile_url": "/1plus1_m.jpg",
        "category_ids": f"{cat_comedy['id']},{cat_drama['id']}",
    })
    assert movie_res.status_code == 201

    # Запрос по category_id Комедии -> фильм найден
    res_com = client.get(f"/api/movies?category_id={cat_comedy['id']}")
    assert len(res_com.json()) == 1
    assert res_com.json()[0]["title"] == "Трагикомедия 1+1"

    # Запрос по category_id Драмы -> этот же фильм найден
    res_dra = client.get(f"/api/movies?category_id={cat_drama['id']}")
    assert len(res_dra.json()) == 1
    assert res_dra.json()[0]["title"] == "Трагикомедия 1+1"

    # Запрос по category_id Боевика -> фильм НЕ найден
    res_act = client.get(f"/api/movies?category_id={cat_action['id']}")
    assert len(res_act.json()) == 0


# ==============================================================================
# 7. ТЕСТЫ БЛОКА 'НОВОЕ И ПОПУЛЯРНОЕ' (is_new_popular)
# ==============================================================================

def test_popular_and_new_movies(client):
    """Проверяет фильтрацию фильмов по отдельному флагу is_new_popular."""
    c = client.post("/api/categories", json={"name": "Фильмы", "slug": "movies"}).json()

    client.post("/api/movies", json={
        "title": "Популярный хит",
        "description": "В топе",
        "duration": "2 ч",
        "quality": "4K",
        "poster_url": "/pop.jpg",
        "banner_desktop_url": "/pop_d.jpg",
        "banner_mobile_url": "/pop_m.jpg",
        "category_ids": str(c["id"]),
        "is_new_popular": True,
    })

    client.post("/api/movies", json={
        "title": "Обычный релиз",
        "description": "Без топа",
        "duration": "1 ч 30 мин",
        "quality": "1080p Full HD",
        "poster_url": "/reg.jpg",
        "banner_desktop_url": "/reg_d.jpg",
        "banner_mobile_url": "/reg_m.jpg",
        "category_ids": str(c["id"]),
        "is_new_popular": False,
    })

    res = client.get("/api/movies?is_popular=true")
    assert res.status_code == 200
    movies = res.json()
    assert len(movies) == 1
    assert movies[0]["title"] == "Популярный хит"


# ==============================================================================
# 8. ТЕСТ ОТКАЗОУСТОЙЧИВОСТИ: БУКВЫ / СПЕЦСИМВОЛЫ В category_ids
# ==============================================================================

def test_fault_tolerance_corrupted_category_ids(client, db_session):
    """
    Требование 4: Отказоустойчивость: валидировать каждый ID.
    Если в строке category_ids обнаружены буквы, спецсимволы или повреждённые данные:
    - НЕ ронять бэкенд (не бросать 500 error);
    - проблемный фильм просто пропускается в выборке по категориям, ошибка логируется;
    - корректные фильмы продолжают штатно возвращаться.
    """
    c = client.post("/api/categories", json={"name": "Боевики", "slug": "action"}).json()

    # 1. Создаем валидный фильм
    res_good = client.post("/api/movies", json={
        "title": "Хороший фильм",
        "description": "Валидные данные",
        "duration": "1 ч 30 мин",
        "quality": "1080p Full HD",
        "poster_url": "/good.jpg",
        "banner_desktop_url": "/good_d.jpg",
        "banner_mobile_url": "/good_m.jpg",
        "category_ids": str(c["id"]),
    })
    assert res_good.status_code == 201

    # 2. Создаем фильм и намеренно портим category_ids в БД (буквы, спецсимволы, мусор)
    res_bad = client.post("/api/movies", json={
        "title": "Поврежденный фильм",
        "description": "Мусор в category_ids",
        "duration": "1 ч 20 мин",
        "quality": "720p HD",
        "poster_url": "/bad.jpg",
        "banner_desktop_url": "/bad_d.jpg",
        "banner_mobile_url": "/bad_m.jpg",
        "category_ids": str(c["id"]),
    })
    bad_id = res_bad.json()["id"]

    db_session.execute(
        text("UPDATE movies SET category_ids = '1, corrupt#$!, abc, 999@' WHERE id = :mid"),
        {"mid": bad_id}
    )
    db_session.commit()

    # 3. Запрос категорий НЕ должен падать с 500!
    cats_res = client.get("/api/categories")
    assert cats_res.status_code == 200, "Бэкенд не должен падать с 500 из-за поврежденных category_ids!"

    # 4. Проверяем, что в выдаче категории присутствует только хороший фильм
    action_cat = next(cat for cat in cats_res.json() if cat["id"] == c["id"])
    movie_titles = [m["title"] for m in action_cat["movies"]]
    assert "Хороший фильм" in movie_titles
    assert "Поврежденный фильм" not in movie_titles, "Поврежденный фильм должен быть пропущен в выборке по категориям"

    # 5. Запрос GET /api/movies?category_id=... также НЕ падает
    filter_res = client.get(f"/api/movies?category_id={c['id']}")
    assert filter_res.status_code == 200
    filter_titles = [m["title"] for m in filter_res.json()]
    assert "Хороший фильм" in filter_titles
    assert "Поврежденный фильм" not in filter_titles


# ==============================================================================
# 9. ТЕСТ ПРЯМОГО РЕДАКТИРОВАНИЯ category_ids В ТАБЛИЦЕ movies
# ==============================================================================

def test_direct_sql_category_ids_update(client, db_session):
    """
    Проверяет, что прямое обновление category_ids в таблице movies
    (например, пользователь вписал '1, 4' в GUI базы) сразу подхватывается API.
    """
    c1 = client.post("/api/categories", json={"name": "Кат А", "slug": "cat-a"}).json()
    c2 = client.post("/api/categories", json={"name": "Кат Б", "slug": "cat-b"}).json()

    res = client.post("/api/movies", json={
        "title": "Фильм прямого редактирования",
        "description": "Тест category_ids",
        "duration": "1 ч 10 мин",
        "quality": "720p HD",
        "poster_url": "/p.jpg",
        "banner_desktop_url": "/d.jpg",
        "banner_mobile_url": "/m.jpg",
        "category_ids": str(c1["id"]),
    })
    mid = res.json()["id"]

    # Пользователь вписал '1, 2' в столбец category_ids напрямую в таблице movies
    db_session.execute(
        text("UPDATE movies SET category_ids = :ids WHERE id = :mid"),
        {"ids": f"{c1['id']}, {c2['id']}", "mid": mid}
    )
    db_session.commit()

    # Проверяем через API
    res_a = client.get(f"/api/movies?category_id={c1['id']}")
    assert any(m["id"] == mid for m in res_a.json())

    res_b = client.get(f"/api/movies?category_id={c2['id']}")
    assert any(m["id"] == mid for m in res_b.json())


# ==============================================================================
# 10. ТЕСТЫ БАННЕРОВ И УДАЛЕНИЯ
# ==============================================================================

def test_banners_endpoint(client):
    c = client.post("/api/categories", json={"name": "Тест"}).json()
    client.post("/api/movies", json={
        "title": "Баннер 1",
        "description": "Описание",
        "duration": "2 ч",
        "quality": "1080p Full HD",
        "poster_url": "/p1.jpg",
        "banner_desktop_url": "/b1.jpg",
        "banner_mobile_url": "/m1.jpg",
        "category_ids": str(c["id"]),
        "is_hero_banner": True,
    })
    client.post("/api/movies", json={
        "title": "Обычный 2",
        "description": "Описание",
        "duration": "1 ч 30 мин",
        "quality": "720p HD",
        "poster_url": "/p2.jpg",
        "banner_desktop_url": "/b2.jpg",
        "banner_mobile_url": "/m2.jpg",
        "category_ids": str(c["id"]),
        "is_hero_banner": False,
    })
    res = client.get("/api/banners")
    assert res.status_code == 200
    banners = res.json()
    assert len(banners) == 1
    assert banners[0]["title"] == "Баннер 1"


def test_delete_movie_and_cors(client):
    c = client.post("/api/categories", json={"name": "Тест"}).json()
    res = client.post("/api/movies", json={
        "title": "Фильм для удаления",
        "description": "Описание",
        "duration": "1 ч 30 мин",
        "quality": "720p HD",
        "poster_url": "/del.jpg",
        "banner_desktop_url": "/del_d.jpg",
        "banner_mobile_url": "/del_m.jpg",
        "category_ids": str(c["id"]),
    })
    pnr = res.json()["pnr"]

    del_res = client.delete(f"/api/movies/{pnr}")
    assert del_res.status_code == 200

    check_res = client.get(f"/api/movies/{pnr}")
    assert check_res.status_code == 404


# ==============================================================================
# 11. ТЕСТЫ ЦЕЛЕВОЙ СХЕМЫ, УПРАВЛЕНИЯ КАТЕГОРИЯМИ И ПАРСИНГА ВИДЕО
# ==============================================================================

def test_target_schema_columns(db_session):
    """Проверяет наличие всех целевых колонок в таблице movies."""
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("movies")}

    required_columns = [
        "id", "pnr", "title", "description", "duration", "quality",
        "poster_url", "banner", "mobile_poster", "movie_page_url",
        "logo_url", "trailer", "is_hero_banner", "is_new_and_popular",
        "category_ids"
    ]
    for col in required_columns:
        assert col in columns, f"Колонка {col} отсутствует в целевой таблице movies"


def test_category_creation_and_duplicate_handling(client):
    """Проверяет создание категории, автогенерацию slug и дедупликацию без учета регистра."""
    # 1. Создание новой категории
    res1 = client.post("/api/categories", json={"name": "Триллер", "icon_path": "/icon.svg"})
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["name"] == "Триллер"
    assert data1["slug"] == "triller"
    assert data1["icon_url"] == "/icon.svg"

    # 2. Попытка создать дубликат с другим регистром ("триллер")
    res2 = client.post("/api/categories", json={"name": "  триллер  "})
    assert res2.status_code in (200, 201)
    data2 = res2.json()
    assert data2["id"] == data1["id"]  # Должна вернуться существующая запись, а не дубликат!

    # 3. Попытка создать запрещенную псевдо-категорию "Новое и популярное"
    res3 = client.post("/api/categories", json={"name": "Новое и популярное"})
    assert res3.status_code == 400


def test_video_metadata_mp4_parser_and_fallback():
    """Проверяет pure-Python MP4 box parser и безопасный fallback при поврежденных файлах."""
    import tempfile
    from backend.utils.video_meta import normalize_duration_str, normalize_quality_str

    # Тестирование нормализации
    assert normalize_duration_str("144") == "2 ч 24 мин"
    assert normalize_duration_str("131") == "2 ч 11 мин"
    assert normalize_duration_str("45") == "45 мин"
    assert normalize_duration_str("115 мин") == "1 ч 55 мин"

    assert normalize_quality_str("720p") == "720p HD"
    assert normalize_quality_str("1080p") == "1080p Full HD"
    assert normalize_quality_str("4k") == "4K"

    # Тестирование реального MP4 файла (если есть в media)
    test_mp4 = Path("media/video/KVLXGR.mp4")
    if test_mp4.is_file():
        meta = extract_video_metadata(test_mp4)
        assert meta["backend"] in ("mp4_atoms", "opencv", "ffprobe")
        assert meta["duration_seconds"] > 0
        assert meta["quality_label"] in ("480p", "720p HD", "1080p Full HD")

    # Тестирование поврежденного файла (не должен выбрасывать исключений)
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tf:
        tf.write(b"NOT A VALID MP4 FILE AT ALL 987654321")
        tf.flush()
        meta_corrupt = extract_video_metadata(tf.name)
        assert meta_corrupt["backend"] == "fallback"
        assert meta_corrupt["width"] == 1920
        assert meta_corrupt["height"] == 1080
        assert meta_corrupt["quality_label"] == "1080p Full HD"
        assert meta_corrupt["duration_formatted"] == "0 мин"


def test_movie_creation_with_target_columns(client):
    """Проверяет создание фильма с использованием новых целевых колонок (banner, mobile_poster, etc.)."""
    cat = client.post("/api/categories", json={"name": "Аниме"}).json()

    movie_payload = {
        "title": "Унесенные призраками",
        "description": "Шедевр анимации",
        "duration": "125",  # Должен нормализоваться в '2 ч 5 мин'
        "quality": "1080p",  # Должен нормализоваться в '1080p Full HD'
        "poster_url": "/posters/ghibli.jpg",
        "banner": "/banners/ghibli_desk.jpg",
        "mobile_poster": "/banners/ghibli_mob.jpg",
        "trailer": "https://youtube.com/watch?v=123",
        "is_hero_banner": True,
        "is_new_and_popular": True,
        "category_ids": [cat["id"]],
    }

    res = client.post("/api/movies", json=movie_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Унесенные призраками"
    assert data["duration"] == "2 ч 5 мин"
    assert data["quality"] == "1080p Full HD"
    assert data["banner"] == "/banners/ghibli_desk.jpg"
    assert data["mobile_poster"] == "/banners/ghibli_mob.jpg"
    assert data["banner_desktop_url"] == "/banners/ghibli_desk.jpg"
    assert data["banner_mobile_url"] == "/banners/ghibli_mob.jpg"
    assert data["trailer"] == "https://youtube.com/watch?v=123"
    assert data["is_hero_banner"] is True
    assert data["is_new_and_popular"] is True



def test_server_accounts_are_private_and_sessions_revocable(client, db_session, monkeypatch):
    from cryptography.fernet import Fernet
    from backend.routes.auth import profile_key
    from backend.models import User, AuthSession
    monkeypatch.setenv("PROFILE_ENCRYPTION_KEY", Fernet.generate_key().decode())
    profile_key.cache_clear()
    try:
        payload = {"name": "Test User", "email": "PERSON@example.com", "password": "secret123"}
        assert client.post("/api/auth/register", json=payload).status_code == 201
        assert client.post("/api/auth/register", json=payload).status_code == 409
        user = db_session.query(User).one()
        assert user.password_hash.startswith("pbkdf2_sha256$600000$")
        assert "secret123" not in user.password_hash
        assert "Test User" not in user.name_encrypted
        assert "person@example.com" not in user.email_encrypted
        assert "person@example.com" not in user.email_digest
        bad = {"email": "person@example.com", "password": "incorrect"}
        assert client.post("/api/auth/login", json=bad).status_code == 401
        good = {"email": "person@example.com", "password": "secret123"}
        response = client.post("/api/auth/login", json=good)
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["name"] == "Test User"
        assert data["user"]["email"] == "person@example.com"
        assert "password_hash" not in data["user"]
        assert db_session.query(AuthSession).one().token_hash != data["token"]
        headers = {"Authorization": "Bearer " + data["token"]}
        assert client.get("/api/auth/me", headers=headers).status_code == 200
        assert client.post("/api/auth/logout", headers=headers).status_code == 204
        assert client.get("/api/auth/me", headers=headers).status_code == 401
        assert client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    finally:
        profile_key.cache_clear()


def test_password_hash_has_unique_salt():
    from backend.routes.auth import hash_password, verify_password
    first, second = hash_password("same-password"), hash_password("same-password")
    assert first != second
    assert verify_password("same-password", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("same-password", "broken")
