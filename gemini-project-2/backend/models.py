"""Модели каталога, пользователей и серверных сессий."""

from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Float, Text, Boolean
from sqlalchemy.orm import declarative_base

from backend.utils.category_parser import parse_category_ids

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email_digest = Column(String(64), unique=True, nullable=False, index=True)
    email_encrypted = Column(Text, nullable=False)
    name_encrypted = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    expires_at = Column(Integer, nullable=False)


class Category(Base):
    """
    Таблица 2: Категории (categories)
    - id: Числовой идентификатор категории
    - name: Название категории (например, 'Фильмы', 'Боевики', 'Драмы')
    - slug: Системный идентификатор (латиница)
    - icon_path: Путь к иконке (nullable). Если NULL/пусто -> отдается fallback-иконка.
    """

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=True)
    icon_path = Column(String(500), nullable=True, default=None)

    @property
    def title(self) -> str:
        """Синоним названия категории для фронтенда."""
        return self.name

    @title.setter
    def title(self, value: str) -> None:
        self.name = value

    @property
    def icon_url(self) -> str:
        """
        Путь к иконке с автоматическим fallback:
        Если icon_path NULL или пуст — возвращает дефолтную тестовую иконку.
        """
        return self.icon_path if self.icon_path else "../IMAGES/icons/test-icon.svg"

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', slug='{self.slug}', icon_path='{self.icon_path}')>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.name,
            "name": self.name,
            "slug": self.slug or "",
            "icon_path": self.icon_path,
            "icon_url": self.icon_url,
        }


class Movie(Base):
    """
    Таблица 1: Фильмы (movies)
    Целевая структура колонок по спецификации:
    - id: уникальный идентификатор (PK)
    - pnr: идентификатор/номер записи (6 символов)
    - title: название
    - description: описание
    - duration: длительность
    - quality: разрешение/качество видео
    - poster_url: ссылка на постер
    - banner: ссылка на баннер (десктоп)
    - mobile_poster: ссылка на мобильный постер
    - movie_page_url: URL страницы фильма
    - logo_url: ссылка на логотип (nullable)
    - trailer: ссылка на трейлер (nullable)
    - is_hero_banner: флаг показа в главном баннере (boolean)
    - is_new_and_popular: флаг 'новое и популярное' (boolean)
    - category_ids: привязка к категориям через ID ("1", "1,4,6")
    """

    __tablename__ = "movies"

    # Основные целевые поля
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pnr = Column(String(6), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    duration = Column(String(50), nullable=False)
    quality = Column(String(50), nullable=False)
    poster_url = Column(String(500), nullable=False)

    banner = Column(String(500), nullable=False)
    mobile_poster = Column(String(500), nullable=False)
    movie_page_url = Column(String(500), nullable=False)
    logo_url = Column(String(500), nullable=True, default=None)
    trailer = Column(String(500), nullable=True, default=None)

    is_hero_banner = Column(Boolean, nullable=False, default=False)
    is_new_and_popular = Column(Boolean, nullable=False, default=False)
    category_ids = Column(String(255), nullable=True, default="")

    # Поля для полной обратной совместимости с существующим кодом и фронтендом
    banner_desktop_url = Column(String(500), nullable=True)
    banner_mobile_url = Column(String(500), nullable=True)
    trailer_url = Column(String(500), nullable=True)
    is_new_popular = Column(Boolean, nullable=False, default=False)
    is_popular = Column(Boolean, nullable=False, default=False)
    is_new = Column(Boolean, nullable=False, default=False)
    rating = Column(Float, nullable=True, default=None)
    year = Column(Integer, nullable=True)
    genre = Column(String(255), nullable=True)
    creator = Column(String(255), nullable=True)
    license = Column(String(255), nullable=True)
    source_url = Column(String(500), nullable=True)

    def __init__(self, **kwargs):
        # Синхронизация синонимов названий полей
        if "banner_desktop_url" in kwargs and "banner" not in kwargs:
            kwargs["banner"] = kwargs["banner_desktop_url"]
        elif "banner" in kwargs and "banner_desktop_url" not in kwargs:
            kwargs["banner_desktop_url"] = kwargs["banner"]

        if "banner_mobile_url" in kwargs and "mobile_poster" not in kwargs:
            kwargs["mobile_poster"] = kwargs["banner_mobile_url"]
        elif "mobile_poster" in kwargs and "banner_mobile_url" not in kwargs:
            kwargs["banner_mobile_url"] = kwargs["mobile_poster"]

        if "trailer_url" in kwargs and "trailer" not in kwargs:
            kwargs["trailer"] = kwargs["trailer_url"]
        elif "trailer" in kwargs and "trailer_url" not in kwargs:
            kwargs["trailer_url"] = kwargs["trailer"]

        pop = (
            kwargs.get("is_new_and_popular")
            or kwargs.get("is_new_popular")
            or kwargs.get("is_popular")
            or False
        )
        kwargs["is_new_and_popular"] = bool(pop)
        kwargs["is_new_popular"] = bool(pop)
        kwargs["is_popular"] = bool(pop)

        super().__init__(**kwargs)

    @property
    def parsed_category_ids(self) -> List[int]:
        """
        Отказоустойчивый парсинг category_ids.
        При обнаружении некорректных данных логирует ошибку и пропускает некорректные ID.
        """
        return parse_category_ids(self.category_ids, movie_info=f"id={self.id} pnr='{self.pnr}'")

    @property
    def category_id(self) -> Optional[int]:
        """Первичный ID категории для обратной совместимости."""
        cids = self.parsed_category_ids
        return cids[0] if cids else None

    def __repr__(self) -> str:
        return f"<Movie(pnr='{self.pnr}', title='{self.title}', category_ids='{self.category_ids}', is_new_and_popular={self.is_new_and_popular})>"

    def to_dict(self, categories_lookup: Optional[Dict[int, Category]] = None) -> dict:
        """
        Сериализация модели в словарь со всеми полями — как новыми целевыми, так и синонимами.
        """
        cids = self.parsed_category_ids
        primary_id = cids[0] if cids else None

        cat_names: List[str] = []
        cat_objs: List[dict] = []
        first_cat_name = None
        first_cat_slug = None

        if categories_lookup:
            for cid in cids:
                if cid in categories_lookup:
                    c = categories_lookup[cid]
                    cat_names.append(c.name)
                    cat_objs.append(c.to_dict())
            if primary_id and primary_id in categories_lookup:
                first_cat_name = categories_lookup[primary_id].name
                first_cat_slug = categories_lookup[primary_id].slug

        effective_banner = self.banner or self.banner_desktop_url or ""
        effective_mobile = self.mobile_poster or self.banner_mobile_url or ""
        effective_trailer = self.trailer or self.trailer_url
        effective_popular = bool(self.is_new_and_popular or self.is_new_popular or self.is_popular)

        return {
            "id": self.id,
            "pnr": self.pnr,
            "title": self.title,
            "description": self.description,
            "duration": self.duration,
            "quality": self.quality,
            "poster_url": self.poster_url,
            # Целевые поля спецификации
            "banner": effective_banner,
            "mobile_poster": effective_mobile,
            "movie_page_url": self.movie_page_url,
            "logo_url": self.logo_url,
            "trailer": effective_trailer,
            "is_hero_banner": bool(self.is_hero_banner),
            "is_new_and_popular": effective_popular,
            "category_ids": cids,
            # Поля совместимости со старым кодом и фронтендом
            "banner_desktop_url": effective_banner,
            "banner_mobile_url": effective_mobile,
            "trailer_url": effective_trailer,
            "is_new_popular": effective_popular,
            "is_popular": effective_popular,
            "is_new": bool(self.is_new),
            "rating": self.rating,
            "category_id": primary_id,
            "category_name": first_cat_name,
            "category_slug": first_cat_slug,
            "category_names": cat_names,
            "categories": cat_objs,
            "categories_str": ",".join(str(cid) for cid in cids),
        }
