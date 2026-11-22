"""
Pydantic схемы для валидации и сериализации данных API кинохостинга Bochflix.
Включает схемы категорий (Category) и фильмов (Movie) с поддержкой Many-to-Many
и обновленной целевой схемы колонок.
"""

import re
import sys
from pathlib import Path
from typing import Optional, Union, List, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BASE_DIR_PATH = Path(__file__).resolve().parent.parent
if str(BASE_DIR_PATH) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PATH))

try:
    from .utils.pnr import is_valid_pnr
    from .utils.video_meta import normalize_duration_str, normalize_quality_str
except ImportError:
    from backend.utils.pnr import is_valid_pnr
    from backend.utils.video_meta import normalize_duration_str, normalize_quality_str


def slugify(text: str) -> str:
    """Генерирует slug из названия категории (поддерживает кириллицу)."""
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    s = text.strip().lower()
    out = []
    for char in s:
        if char in translit:
            out.append(translit[char])
        elif char.isalnum():
            out.append(char)
        elif char in (' ', '-', '_'):
            out.append('-')
    res = re.sub(r'-+', '-', ''.join(out)).strip('-')
    return res or "category"


# ==============================================================================
# СХЕМЫ КАТЕГОРИЙ
# ==============================================================================

class CategoryBase(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Название категории")
    title: Optional[str] = Field(None, max_length=100, description="Заголовок категории (синоним name)")
    slug: Optional[str] = Field(None, max_length=100, description="Уникальный системный slug")
    icon_path: Optional[str] = Field(None, max_length=500, description="Путь к иконке категории (может быть NULL)")
    icon_url: Optional[str] = Field(None, max_length=500, description="URL иконки категории")


class CategoryCreate(CategoryBase):
    @model_validator(mode="after")
    def ensure_name_and_slug(self) -> "CategoryCreate":
        # Если передан title, но не name — синхронизируем
        if not self.name and self.title:
            self.name = self.title
        elif not self.title and self.name:
            self.title = self.name

        if not self.name or not self.name.strip():
            raise ValueError("Название категории (name или title) обязательно")

        self.name = self.name.strip()
        self.title = self.name

        if not self.slug or not self.slug.strip():
            self.slug = slugify(self.name)
        else:
            cleaned = re.sub(r'[^a-z0-9_-]', '', self.slug.strip().lower())
            self.slug = cleaned or slugify(self.name)

        if not self.icon_path and self.icon_url:
            self.icon_path = self.icon_url
        return self


class CategoryCatalogItem(BaseModel):
    """
    Легковесная схема категории для иконочного каталога (GET /api/catalog/categories).
    """
    id: int
    title: str = Field(..., description="Название категории")
    name: Optional[str] = None
    slug: Optional[str] = None
    icon_path: Optional[str] = Field(None, description="Путь к иконке категории (может быть NULL)")
    icon_url: Optional[str] = Field(None, description="URL иконки с fallback на дефолтную")

    model_config = ConfigDict(from_attributes=True)


class CategoryRead(BaseModel):
    id: int
    title: str
    name: Optional[str] = None
    slug: str
    icon_path: Optional[str] = None
    icon_url: Optional[str] = None
    movies_count: Optional[int] = Field(None, description="Количество фильмов в категории")
    movies: Optional[List[Any]] = Field(None, description="Фильмы категории")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# СХЕМЫ ФИЛЬМОВ
# ==============================================================================

class MovieCatalogItem(BaseModel):
    """
    Схема фильма для каталога и горизонтальных треков.
    """

    id: Optional[int] = Field(None, description="ID фильма")
    pnr: str = Field(..., description="Уникальный 6-значный PNR идентификатор фильма")
    title: str = Field(..., description="Название фильма")
    poster_url: str = Field(..., description="Путь/URL к постеру")
    quality: str = Field(..., description="Качество видео (например, '1080p Full HD', '4K')")
    duration: Union[int, str] = Field(..., description="Длительность (например, '2 ч 29 мин')")
    movie_page_url: str = Field(..., description="Ссылка на детальную страницу (/movie/video/{pnr}.mp4)")

    # Целевые поля по ТЗ
    banner: Optional[str] = Field(None, description="Ссылка на баннер (десктоп)")
    mobile_poster: Optional[str] = Field(None, description="Ссылка на мобильный постер")
    trailer: Optional[str] = Field(None, description="Ссылка на трейлер")
    is_hero_banner: bool = Field(False, description="Флаг показа в главном слайдере")
    is_new_and_popular: bool = Field(False, description="Флаг 'Новое и популярное'")

    # Поля обратной совместимости
    banner_desktop_url: Optional[str] = None
    banner_mobile_url: Optional[str] = None
    trailer_url: Optional[str] = None
    is_new_popular: bool = Field(False, description="Флаг 'Новое и популярное'")
    is_popular: bool = Field(False, description="Флаг 'Новое и популярное' (совместимость)")
    is_new: bool = Field(False, description="Флаг свежего релиза")

    category_id: Optional[Union[int, str]] = Field(None, description="ID основной категории")
    category_name: Optional[str] = Field(None, description="Название основной категории")
    category_slug: Optional[str] = Field(None, description="Slug основной категории")

    category_ids: Optional[List[int]] = Field(default_factory=list, description="Список всех привязанных категорий")
    category_names: Optional[List[str]] = Field(default_factory=list, description="Названия всех категорий")
    categories: Optional[List[CategoryCatalogItem]] = Field(default_factory=list, description="Объекты категорий")
    categories_str: Optional[str] = Field(None, description="Строка со всеми категориями через запятую")

    description: Optional[str] = Field(None, description="Краткое описание")
    rating: Optional[float] = Field(None, description="Рейтинг фильма")

    model_config = ConfigDict(from_attributes=True)

    @field_validator("category_id", mode="before")
    @classmethod
    def normalize_category_id(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        s = str(v).strip()
        first_num = s.split(",")[0].strip()
        if first_num.isdigit():
            return int(first_num)
        return None


class CategoryWithMovies(BaseModel):
    """
    Схема категории со списком фильмов для Infinite Scroll (GET /api/categories).
    """
    id: int
    title: str = Field(..., description="Название категории")
    name: Optional[str] = None
    slug: str
    icon_path: Optional[str] = None
    icon_url: Optional[str] = None
    movies: List[MovieCatalogItem] = Field(default_factory=list, description="Список фильмов категории")

    model_config = ConfigDict(from_attributes=True)


class MovieBannerItem(BaseModel):
    """
    Схема для элементов промо-слайдера (GET /api/banners).
    Фильтрует только фильмы с флагом is_hero_banner = True.
    """

    id: Optional[int] = Field(None, description="ID фильма")
    pnr: str = Field(..., description="Уникальный 6-значный PNR идентификатор фильма")
    title: str = Field(..., description="Название фильма")

    # Целевые поля
    banner: Optional[str] = Field(None, description="Баннер десктоп")
    mobile_poster: Optional[str] = Field(None, description="Мобильный баннер")
    # Поля совместимости со слайдером
    banner_desktop_url: str = Field(..., description="Баннер 16:9 для десктопа")
    banner_mobile_url: str = Field(..., description="Баннер 1.2:1 (~6:5) для мобильных устройств")
    movie_page_url: str = Field(..., description="Ссылка на страницу фильма")
    is_hero_banner: bool = Field(True, description="Флаг промо-баннера")

    category_id: Optional[Union[int, str]] = None
    description: Optional[str] = None
    quality: Optional[str] = None
    duration: Optional[Union[int, str]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("category_id", mode="before")
    @classmethod
    def normalize_category_id(cls, v):
        if v is None:
            return None
        if isinstance(v, int):
            return v
        s = str(v).strip()
        first_num = s.split(",")[0].strip()
        if first_num.isdigit():
            return int(first_num)
        return None


class MovieDetail(BaseModel):
    """
    Полная схема фильма со всеми метаданными целевой схемы и совместимыми полями.
    """

    id: int
    pnr: str
    title: str
    description: str
    duration: Union[int, str]
    quality: str
    poster_url: str

    # Целевые поля по ТЗ
    banner: Optional[str] = None
    mobile_poster: Optional[str] = None
    movie_page_url: str
    logo_url: Optional[str] = None
    trailer: Optional[str] = None
    is_hero_banner: bool = False
    is_new_and_popular: bool = False
    category_ids: Optional[List[int]] = Field(default_factory=list)

    # Поля совместимости
    banner_desktop_url: str
    banner_mobile_url: str
    trailer_url: Optional[str] = None
    is_popular: bool = False
    is_new_popular: bool = False
    is_new: bool = False

    category_id: Optional[int] = None
    category_names: Optional[List[str]] = Field(default_factory=list)
    categories: Optional[List[CategoryCatalogItem]] = Field(default_factory=list)
    categories_str: Optional[str] = None
    rating: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class MovieCreate(BaseModel):
    """
    Схема входных данных для добавления нового фильма в БД.
    Поддерживает как целевые названия полей (banner, mobile_poster, trailer, is_new_and_popular),
    так и названия полей обратной совместимости (banner_desktop_url, banner_mobile_url, trailer_url, is_new_popular).
    """

    title: str = Field(..., min_length=1, description="Название фильма")
    description: str = Field(..., min_length=1, description="Описание фильма")
    duration: Union[int, str] = Field(..., description="Длительность (например, '2 ч 15 мин')")
    quality: str = Field(..., min_length=1, description="Качество ('1080p Full HD', '4K')")
    poster_url: str = Field(..., min_length=1, description="URL или путь к постеру")

    # Целевые поля
    banner: Optional[str] = Field(None, description="URL или путь к десктопному баннеру")
    mobile_poster: Optional[str] = Field(None, description="URL или путь к мобильному постеру")
    trailer: Optional[str] = Field(None, description="URL или путь к трейлеру")
    is_new_and_popular: bool = Field(False, description="Показывать в блоке 'Новое и популярное'")

    # Поля совместимости
    banner_desktop_url: Optional[str] = Field(None, description="URL баннера 16:9")
    banner_mobile_url: Optional[str] = Field(None, description="URL баннера 1.2:1")
    trailer_url: Optional[str] = Field(None, description="URL трейлера")
    is_new_popular: bool = Field(False, description="Показывать в блоке 'Новое и популярное'")
    is_popular: bool = Field(False, description="Показывать в блоке 'Новое и популярное' (совместимость)")
    is_hero_banner: bool = Field(False, description="Показывать в главном промо-слайдере")
    is_new: bool = Field(False, description="Пометить как свежий релиз")

    movie_page_url: Optional[str] = Field(
        None, description="Ссылка на страницу фильма (по умолчанию /movie/video/{pnr}.mp4)"
    )

    # Гибкий ввод категорий
    categories: Optional[Union[str, List[Union[str, int]]]] = Field(
        None, description="Категории: строка 'Комедии, Драмы' или массив ['Комедии', 'Драмы']"
    )
    category_ids: Optional[Union[str, List[Union[str, int]]]] = Field(
        None, description="Список ID категорий или строка через запятую '1, 4'"
    )
    category: Optional[Union[str, int]] = Field(
        None, description="Одиночная категория (название или ID)"
    )
    category_id: Optional[Union[str, int]] = Field(
        None, description="Одиночный ID категории"
    )

    pnr: Optional[str] = Field(
        None, description="PNR фильма (если не передан, генерируется автоматически)"
    )
    rating: Optional[float] = None
    logo_url: Optional[str] = None

    @model_validator(mode="after")
    def sync_banner_and_flags(self) -> "MovieCreate":
        # Синхронизация баннеров
        if not self.banner and self.banner_desktop_url:
            self.banner = self.banner_desktop_url
        elif not self.banner_desktop_url and self.banner:
            self.banner_desktop_url = self.banner

        if not self.mobile_poster and self.banner_mobile_url:
            self.mobile_poster = self.banner_mobile_url
        elif not self.banner_mobile_url and self.mobile_poster:
            self.banner_mobile_url = self.mobile_poster

        if not self.banner:
            raise ValueError("Баннер (banner или banner_desktop_url) обязателен")
        if not self.mobile_poster:
            raise ValueError("Мобильный постер (mobile_poster или banner_mobile_url) обязателен")

        # Синхронизация трейлера
        if not self.trailer and self.trailer_url:
            self.trailer = self.trailer_url
        elif not self.trailer_url and self.trailer:
            self.trailer_url = self.trailer

        # Синхронизация флага популярности
        pop = self.is_new_and_popular or self.is_new_popular or self.is_popular
        self.is_new_and_popular = bool(pop)
        self.is_new_popular = bool(pop)
        self.is_popular = bool(pop)

        # Нормализация duration и quality
        self.duration = normalize_duration_str(self.duration)
        self.quality = normalize_quality_str(self.quality)

        return self

    @field_validator("pnr")
    @classmethod
    def validate_pnr(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not is_valid_pnr(value):
            raise ValueError(
                "PNR должен состоять ровно из 6 символов (цифры 0-9 и заглавные согласные BCDFGHJKLMNPQRSTVWXYZ)"
            )
        return value.upper() if value else None

    def get_all_category_inputs(self) -> List[Any]:
        """Возвращает все переданные категории для парсинга."""
        items = []
        if self.categories is not None:
            items.append(self.categories)
        if self.category_ids is not None:
            items.append(self.category_ids)
        if self.category is not None:
            items.append(self.category)
        if self.category_id is not None:
            items.append(self.category_id)
        return items
