"""
Маршруты API для фильмов, категорий, каталога и промо-слайдера (FastAPI).
Архитектура строго из 2 таблиц (movies и categories), без промежуточных M2M-таблиц.

Реализует:
- GET /api/categories: непустые категории с фильмами (offset/limit). Пустые категории фильтруются!
- GET /api/catalog/categories: непустые категории каталога с fallback-иконками.
- GET /api/movies: выдача фильмов с фильтрацией по категории и флагу 'Новое и популярное'.
- GET /api/banners: промо-баннеры (is_hero_banner = True).
- POST/DELETE /api/movies: добавление и удаление фильмов.
- POST /api/categories: добавление новых категорий с валидацией дубликатов и генерацией slug.
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

BASE_DIR_PATH = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PATH))

try:
    from ..database import get_db
    from ..models import Movie, Category
    from ..schemas import (
        MovieCatalogItem,
        MovieBannerItem,
        MovieDetail,
        MovieCreate,
        CategoryRead,
        CategoryCreate,
        CategoryCatalogItem,
        CategoryWithMovies,
        slugify,
    )
    from ..utils.pnr import generate_pnr, is_valid_pnr
    from ..utils.category_parser import parse_category_ids, is_popular_category, format_category_ids
except ImportError:
    from backend.database import get_db
    from backend.models import Movie, Category
    from backend.schemas import (
        MovieCatalogItem,
        MovieBannerItem,
        MovieDetail,
        MovieCreate,
        CategoryRead,
        CategoryCreate,
        CategoryCatalogItem,
        CategoryWithMovies,
        slugify,
    )
    from backend.utils.pnr import generate_pnr, is_valid_pnr
    from backend.utils.category_parser import parse_category_ids, is_popular_category, format_category_ids

logger = logging.getLogger("bochflix.api")
router = APIRouter(tags=["Movies, Banners & Categories"])


def _generate_unique_pnr(db: Session, max_attempts: int = 50) -> str:
    """Генерирует PNR, которого еще нет в базе данных."""
    for _ in range(max_attempts):
        candidate = generate_pnr(6)
        exists = db.query(Movie.id).filter(Movie.pnr == candidate).first()
        if not exists:
            return candidate
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Не удалось сгенерировать уникальный PNR после нескольких попыток",
    )


def _get_categories_lookup(db: Session) -> Dict[int, Category]:
    """Возвращает кэш всех категорий по ID."""
    cats = db.query(Category).all()
    return {c.id: c for c in cats}


def _generate_unique_slug(db: Session, base_slug: str, exclude_id: Optional[int] = None) -> str:
    """Генерирует уникальный slug, добавляя числовой суффикс при коллизии."""
    candidate = base_slug
    counter = 1
    while True:
        q = db.query(Category.id).filter(Category.slug == candidate)
        if exclude_id is not None:
            q = q.filter(Category.id != exclude_id)
        if not q.first():
            return candidate
        counter += 1
        candidate = f"{base_slug}-{counter}"


def get_or_create_category(
    db: Session,
    name: str,
    slug: Optional[str] = None,
    icon_path: Optional[str] = None,
) -> Tuple[Category, bool]:
    """
    Поиск или создание категории:
    - Проверка дубликатов по имени без учета регистра (с полной поддержкой кириллицы).
    - Автоматическая генерация slug при необходимости.
    - Возвращает кортеж (Category, was_created: bool).
    """
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Название категории не может быть пустым")

    base_slug = slug or slugify(clean_name)
    all_cats = db.query(Category).all()

    # Сравнение в Python гарантирует корректную дедупликацию кириллицы в SQLite
    existing = next(
        (
            c for c in all_cats
            if c.name.strip().lower() == clean_name.lower()
            or (c.slug and c.slug.strip().lower() == base_slug.lower())
        ),
        None,
    )

    if existing:
        # Если передан icon_path, а в базе его нет — обновляем
        if icon_path and not existing.icon_path:
            existing.icon_path = icon_path
            db.commit()
            db.refresh(existing)
        return existing, False

    unique_slug = _generate_unique_slug(db, base_slug)

    new_cat = Category(
        name=clean_name,
        slug=unique_slug,
        icon_path=icon_path,
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat, True


def _group_movies_by_category(db: Session, cats_lookup: Dict[int, Category]) -> Dict[int, List[MovieCatalogItem]]:
    """
    Группирует валидные фильмы по ID категорий.
    Отказоустойчивость: проблемные фильмы с некорректными category_ids
    безопасно логируются и пропускаются без падения сервера (без 500 error).
    """
    movies = db.query(Movie).order_by(Movie.id.desc()).all()
    movies_by_cat: Dict[int, List[MovieCatalogItem]] = {}

    for m in movies:
        valid_ids = parse_category_ids(m.category_ids, movie_info=f"id={m.id} pnr='{m.pnr}'")
        if not valid_ids:
            continue

        item = MovieCatalogItem(**m.to_dict(cats_lookup))
        for cid in valid_ids:
            if cid in cats_lookup:
                movies_by_cat.setdefault(cid, []).append(item)

    return movies_by_cat


# ==============================================================================
# 1. КАТЕГОРИИ
# ==============================================================================

@router.get(
    "/catalog/categories",
    response_model=List[CategoryCatalogItem],
    summary="Список непустых категорий для каталога иконок",
)
def get_catalog_categories(db: Session = Depends(get_db)):
    """
    Возвращает список непустых категорий каталога (id, title, icon_url, icon_path)
    для верхнего иконочного трека <section class="main__catalog">.

    ТРЕБОВАНИЯ:
    1. Исключаются категории 'Новое' и 'Популярное' (обрабатываются отдельно).
    2. Фильтрация пустых категорий: категории, к которым не привязан ни один валидный фильм,
       НЕ отправляются на фронтенд для отрисовки.
    3. При отсутствии icon_path отдается fallback на дефолтную иконку.
    """
    cats_lookup = _get_categories_lookup(db)
    movies_by_cat = _group_movies_by_category(db, cats_lookup)

    all_categories = db.query(Category).order_by(Category.id.asc()).all()
    non_empty = [
        cat for cat in all_categories
        if not is_popular_category(cat.name)
        and not (cat.slug and is_popular_category(cat.slug))
        and cat.id in movies_by_cat
        and len(movies_by_cat[cat.id]) > 0
    ]

    return [
        CategoryCatalogItem(
            id=cat.id,
            title=cat.title,
            name=cat.name,
            slug=cat.slug,
            icon_path=cat.icon_path,
            icon_url=cat.icon_url,
        )
        for cat in non_empty
    ]


@router.get(
    "/categories",
    response_model=List[CategoryWithMovies],
    summary="Список непустых категорий с пагинацией и фильмами (Infinite Scroll)",
)
def get_categories_paginated(
    offset: int = Query(0, ge=0, description="Смещение пагинации категорий"),
    limit: int = Query(10, ge=1, le=50, description="Количество категорий в порции"),
    exclude_popular: bool = Query(True, description="Исключать категорию 'Новое и популярное'"),
    db: Session = Depends(get_db),
):
    """
    Возвращает порцию категорий (offset/limit) вместе со списком фильмов.

    ТРЕБОВАНИЯ:
    1. Исключаются категории 'Новое' и 'Популярное' (выводятся в отдельной фиксированной секции).
    2. Фильтрация пустых категорий: категории, к которым не привязан ни один фильм
       (или фильмы которых не прошли валидацию), НЕ отправляются на фронтенд.
    3. Пагинация (offset/limit) применяется строго к списку непустых категорий.
    """
    cats_lookup = _get_categories_lookup(db)
    movies_by_cat = _group_movies_by_category(db, cats_lookup)

    all_categories = db.query(Category).order_by(Category.id.asc()).all()
    non_empty_categories = []

    for cat in all_categories:
        if exclude_popular and (is_popular_category(cat.name) or (cat.slug and is_popular_category(cat.slug))):
            continue
        cat_movies = movies_by_cat.get(cat.id, [])
        if not cat_movies:
            # Пустая категория -> пропускаем!
            continue
        non_empty_categories.append((cat, cat_movies))

    paged = non_empty_categories[offset: offset + limit]

    result = []
    for cat, cat_movies in paged:
        result.append(
            CategoryWithMovies(
                id=cat.id,
                title=cat.title,
                name=cat.name,
                slug=cat.slug or "",
                icon_path=cat.icon_path,
                icon_url=cat.icon_url,
                movies=cat_movies,
            )
        )
    return result


@router.post(
    "/categories",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создание новой категории",
)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    """
    Создает новую категорию с проверкой на дубликаты по имени (case-insensitive)
    и автогенерацией уникального slug.
    """
    clean_name = (payload.name or payload.title or "").strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название категории обязательно",
        )

    if is_popular_category(clean_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория 'Новое и популярное' управляется отдельным системным флагом фильма (is_new_and_popular) и не создается как отдельная категория.",
        )

    cat, created = get_or_create_category(
        db=db,
        name=clean_name,
        slug=payload.slug,
        icon_path=payload.icon_path or payload.icon_url,
    )

    return CategoryRead(
        id=cat.id,
        title=cat.title,
        name=cat.name,
        slug=cat.slug or "",
        icon_path=cat.icon_path,
        icon_url=cat.icon_url,
        movies_count=0,
    )


# ==============================================================================
# 2. ФИЛЬМЫ (КАТАЛОГ И ТРЕКИ)
# ==============================================================================

@router.get(
    "/movies",
    response_model=List[MovieCatalogItem],
    summary="Список фильмов для каталога и горизонтальных треков",
)
def get_movies(
    category_id: Optional[int] = Query(None, description="Фильтр по ID категории"),
    category_slug: Optional[str] = Query(None, description="Фильтр по slug категории"),
    is_popular: Optional[bool] = Query(None, description="Фильтр фильмов для 'Новое и популярное'"),
    is_new_popular: Optional[bool] = Query(None, description="Фильтр фильмов для 'Новое и популярное'"),
    limit: int = Query(50, ge=1, le=100, description="Количество фильмов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    db: Session = Depends(get_db),
):
    """
    Возвращает список фильмов для каталога и треков.
    Поддерживает фильтрацию по category_id, category_slug и флагу is_new_and_popular.
    Отказоустойчивость: фильмы с поврежденными category_ids пропускаются и логируются.
    """
    cats_lookup = _get_categories_lookup(db)
    query = db.query(Movie)

    popular_flag = is_popular if is_popular is not None else is_new_popular
    if popular_flag is not None:
        query = query.filter(
            (Movie.is_new_and_popular == popular_flag) | (Movie.is_new_popular == popular_flag)
        )

    movies = query.order_by(Movie.id.desc()).all()

    # Поиск целевого ID категории, если передан category_slug
    target_category_id = category_id
    if target_category_id is None and category_slug:
        cat_match = next((c for c in cats_lookup.values() if c.slug == category_slug), None)
        if cat_match:
            target_category_id = cat_match.id
        else:
            return []

    filtered_items: List[MovieCatalogItem] = []
    for m in movies:
        valid_ids = parse_category_ids(m.category_ids, movie_info=f"id={m.id} pnr='{m.pnr}'")

        if target_category_id is not None:
            if target_category_id not in valid_ids:
                continue
        elif popular_flag is None and not valid_ids:
            # Для общего каталога пропускаем фильмы без валидных категорий
            continue

        filtered_items.append(MovieCatalogItem(**m.to_dict(cats_lookup)))

    return filtered_items[offset: offset + limit]


# ==============================================================================
# 3. БАННЕРЫ (ПРОМО-СЛАЙДЕР)
# ==============================================================================

@router.get(
    "/banners",
    response_model=List[MovieBannerItem],
    summary="Список фильмов для главного промо-слайдера",
)
def get_banners(
    limit: int = Query(10, ge=1, le=20, description="Количество слайдов"),
    db: Session = Depends(get_db),
):
    """
    Возвращает фильмы для промо-слайдера.
    ПРАВИЛО: Возвращаются ТОЛЬКО фильмы с флагом is_hero_banner = True.
    """
    cats_lookup = _get_categories_lookup(db)
    banners = (
        db.query(Movie)
        .filter(Movie.is_hero_banner == True)
        .order_by(Movie.id.desc())
        .limit(limit)
        .all()
    )
    return [MovieBannerItem(**b.to_dict(cats_lookup)) for b in banners]


# ==============================================================================
# 4. ДЕТАЛКА, СОЗДАНИЕ И УДАЛЕНИЕ ФИЛЬМА
# ==============================================================================

@router.get(
    "/movies/{pnr}",
    response_model=MovieDetail,
    summary="Получение полной информации о фильме по PNR",
)
def get_movie_by_pnr(pnr: str, db: Session = Depends(get_db)):
    """Возвращает детальную карточку фильма по его уникальному PNR коду."""
    clean_pnr = pnr.strip().upper()
    movie = db.query(Movie).filter(Movie.pnr == clean_pnr).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фильм с PNR '{clean_pnr}' не найден",
        )
    cats_lookup = _get_categories_lookup(db)
    return MovieDetail(**movie.to_dict(cats_lookup))


@router.post(
    "/movies",
    response_model=MovieDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Добавление нового фильма в базу данных",
)
def create_movie(payload: MovieCreate, db: Session = Depends(get_db)):
    """
    Создает новую запись фильма в таблице movies.
    Поддерживает ввод категорий ID через запятую ("1,4,6") или массивом [1, 4].
    Если переданы названия категорий (например, 'Боевики, Драмы') — находит их ID
    или автоматически создает категорию в таблице categories.
    """
    pnr = payload.pnr
    if not pnr:
        pnr = _generate_unique_pnr(db)
    else:
        pnr = pnr.strip().upper()
        if not is_valid_pnr(pnr):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PNR должен состоять из 6 цифр и латинских согласных (BCDFGHJKLMNPQRSTVWXYZ)",
            )
        existing = db.query(Movie.id).filter(Movie.pnr == pnr).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Фильм с PNR '{pnr}' уже существует в базе данных",
            )

    # Разрешаем переданные категории к списку числовых ID
    all_inputs = payload.get_all_category_inputs()
    resolved_ids: List[int] = []
    cats_lookup = _get_categories_lookup(db)

    is_pop = payload.is_new_and_popular or payload.is_new_popular or payload.is_popular

    for raw in all_inputs:
        if raw is None:
            continue
        if isinstance(raw, (list, tuple)):
            for item in raw:
                s_item = str(item).strip()
                if s_item.isdigit():
                    resolved_ids.append(int(s_item))
                elif s_item:
                    if is_popular_category(s_item):
                        is_pop = True
                        continue
                    cat, _ = get_or_create_category(db, s_item)
                    cats_lookup[cat.id] = cat
                    resolved_ids.append(cat.id)
        else:
            s_raw = str(raw).strip()
            for part in s_raw.replace(";", ",").split(","):
                part_clean = part.strip()
                if not part_clean:
                    continue
                if part_clean.isdigit():
                    resolved_ids.append(int(part_clean))
                else:
                    if is_popular_category(part_clean):
                        is_pop = True
                        continue
                    cat, _ = get_or_create_category(db, part_clean)
                    cats_lookup[cat.id] = cat
                    resolved_ids.append(cat.id)

    # Дедупликация и форматирование в строку "1,4,6"
    clean_cat_ids_str = format_category_ids(resolved_ids)

    movie_page_url = payload.movie_page_url or f"/movie/video/{pnr}.mp4"
    desktop_banner = payload.banner or payload.banner_desktop_url or ""
    mobile_banner = payload.mobile_poster or payload.banner_mobile_url or ""
    trailer_val = payload.trailer or payload.trailer_url

    movie = Movie(
        pnr=pnr,
        title=payload.title.strip(),
        description=payload.description.strip(),
        duration=str(payload.duration).strip(),
        quality=payload.quality.strip(),
        poster_url=payload.poster_url.strip(),
        banner=desktop_banner.strip(),
        mobile_poster=mobile_banner.strip(),
        banner_desktop_url=desktop_banner.strip(),
        banner_mobile_url=mobile_banner.strip(),
        movie_page_url=movie_page_url.strip(),
        category_ids=clean_cat_ids_str,
        is_new_and_popular=bool(is_pop),
        is_new_popular=bool(is_pop),
        is_popular=bool(is_pop),
        is_hero_banner=bool(payload.is_hero_banner),
        is_new=bool(payload.is_new),
        rating=payload.rating,
        logo_url=payload.logo_url.strip() if payload.logo_url else None,
        trailer=trailer_val.strip() if trailer_val else None,
        trailer_url=trailer_val.strip() if trailer_val else None,
    )

    try:
        db.add(movie)
        db.commit()
        db.refresh(movie)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка целостности данных при сохранении фильма: {exc}",
        )

    return MovieDetail(**movie.to_dict(cats_lookup))


@router.delete(
    "/movies/{pnr}",
    status_code=status.HTTP_200_OK,
    summary="Удаление фильма по PNR",
)
def delete_movie(pnr: str, db: Session = Depends(get_db)):
    """Удаляет фильм из базы данных по его PNR."""
    clean_pnr = pnr.strip().upper()
    movie = db.query(Movie).filter(Movie.pnr == clean_pnr).first()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Фильм с PNR '{clean_pnr}' не найден",
        )
    db.delete(movie)
    db.commit()
    return {"status": "success", "message": f"Фильм с PNR {clean_pnr} успешно удален"}
