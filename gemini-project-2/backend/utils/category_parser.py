"""
Утилита для парсинга и валидации категорий фильмов.
Реализует требования:
1. Парсинг поля category_ids (например: "1", "1,3,5") в список целых чисел (List[int]).
2. Отказоустойчивость: валидация каждого ID. Если в строке обнаружены буквы, спецсимволы
   или поврежденные данные — не ронять бэкенд (не бросать 500 error), логировать ошибку
   и пропускать проблемный фильм в выборке по категориям.
3. Проверка системного статуса 'Новое и популярное'.
"""

import logging
import re
from typing import Any, List, Union

logger = logging.getLogger("bochflix.categories")

POPULAR_SLUGS = {"new", "popular", "new-popular", "novoe", "populyarnoe"}
POPULAR_NAMES = {"новое", "популярное", "новое и популярное", "новое & популярное"}


def is_popular_category(name_or_slug: str) -> bool:
    """Проверяет, относится ли категория к 'Новое' / 'Популярное'."""
    if not name_or_slug:
        return False
    s = name_or_slug.strip().lower()
    return s in POPULAR_NAMES or s in POPULAR_SLUGS


def parse_category_ids(raw: Any, movie_info: str = "") -> List[int]:
    """
    Парсит поле category_ids (например: "1", "1,3,5", " 1 , 4 ") в список целых чисел List[int].

    Отказоустойчивость:
    - Валидирует каждый токен.
    - Если в строке category_ids обнаружены буквы, спецсимволы или поврежденные данные:
      логирует ошибку с идентификатором фильма,
      фильм пропускается в выборке по категориям (возвращает []),
      бэкенд НЕ падает (никаких 500 ошибок).
    """
    if raw is None:
        return []

    # Если уже целое число
    if isinstance(raw, int):
        return [raw] if raw > 0 else []

    # Если передан массив чисел/строк
    if isinstance(raw, (list, tuple, set)):
        parsed = []
        for item in raw:
            s_item = str(item).strip()
            if not s_item.isdigit() or int(s_item) <= 0:
                logger.error(
                    "[Отказоустойчивость] В category_ids обнаружены некорректные данные: %r у фильма %s. Фильм пропущен.",
                    raw, movie_info or "без ID"
                )
                return []
            parsed.append(int(s_item))
        return sorted(list(set(parsed)))

    s = str(raw).strip()
    if not s:
        return []

    # Токены, разделенные запятой
    tokens = [t.strip() for t in s.replace(";", ",").split(",") if t.strip()]
    if not tokens:
        return []

    parsed_ids = []
    for t in tokens:
        if not t.isdigit() or int(t) <= 0:
            logger.error(
                "[Отказоустойчивость] В строке category_ids обнаружены буквы/спецсимволы/повреждения: %r (токен %r) у фильма %s. Фильм пропущен в выборке по категориям.",
                s, t, movie_info or "без ID"
            )
            return []
        parsed_ids.append(int(t))

    return sorted(list(set(parsed_ids)))


def format_category_ids(category_ids: Union[str, List[int], int, None]) -> str:
    """
    Нормализует список или строку ID категорий в стандартный вид '1,4,6'.
    """
    ids = parse_category_ids(category_ids)
    return ",".join(str(cid) for cid in ids)
