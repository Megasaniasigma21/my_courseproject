#!/usr/bin/env python3
"""
CLI-утилита для интерактивного наполнения и управления базой данных кинохостинга Bochflix.
Реализует пошаговый мастер добавления фильмов:
1. Генерация PNR (цифры 0-9 и латинские согласные);
2. Запрос пути к исходному видеофайлу;
3. Автоматический парсинг метаданных видео (длительность 'X ч Y мин', качество '1080p Full HD' и т.д.);
4. Перемещение и переименование видеофайла в media/video/<PNR>.mp4;
5. Ручной ввод названия, описания, баннеров, выбор категории и флага is_hero_banner;
6. Предпоказ карточки и подтверждение сохранения в БД.
"""

import sys
import shutil
import argparse
from pathlib import Path
from typing import Optional, List, Tuple

from backend.config import BASE_DIR, settings
from backend.database import SessionLocal, init_db
from backend.models import Movie, Category
from backend.utils.pnr import generate_pnr, is_valid_pnr, PNR_ALPHABET, PNR_LENGTH
from backend.utils.video_meta import (
    extract_video_metadata,
    format_duration,
    map_resolution_to_label,
    normalize_duration_str,
    normalize_quality_str,
)

VIDEO_STORAGE_DIR = BASE_DIR / "media" / "video"
POSTER_STORAGE_DIR = BASE_DIR / "media" / "posters"
BANNER_STORAGE_DIR = BASE_DIR / "media" / "banners"


def print_banner():
    print("""
====================================================================
          BOCHFLIX — УТИЛИТА НАПОЛНЕНИЯ И УПРАВЛЕНИЯ БД
====================================================================
""")


def clean_input_path(raw_path: str) -> str:
    """Очищает путь от кавычек и экранированных пробелов при перетаскивании из Finder."""
    val = raw_path.strip().strip("'\"")
    # Убираем экранирование обратными слэшами на macOS/Linux (e.g. My\ Video.mp4)
    val = val.replace("\\ ", " ")
    return val


def prompt_non_empty(prompt_text: str, default: Optional[str] = None) -> str:
    """Запрашивает у пользователя непустую строку с возможностью дефолтного значения."""
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            val = input(f"{prompt_text}{suffix}: ").strip()
            if not val and default is not None:
                return default
            if val:
                return val
            print("  [!] Поле не может быть пустым. Пожалуйста, введите значение.")
        except (KeyboardInterrupt, EOFError):
            print("\n  [!] Ввод прерван.")
            sys.exit(0)


def process_media_file(user_input: str, media_subdir: str, pnr: str, suffix: str) -> str:
    """
    Если пользователь указал локальный файл на диске, копирует его в media/{media_subdir}/
    и возвращает публичный веб-URL /media/{media_subdir}/<PNR>_<suffix>.<ext>.
    """
    clean_path = clean_input_path(user_input)
    expanded = Path(clean_path).expanduser().resolve()
    if expanded.is_file():
        ext = expanded.suffix.lower() or ".webp"
        dest_filename = f"{pnr}_{suffix}{ext}"
        dest_dir = BASE_DIR / "media" / media_subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / dest_filename
        if expanded != dest_file:
            shutil.copy2(expanded, dest_file)
        web_url = f"/media/{media_subdir}/{dest_filename}"
        print(f"  [+] Файл скопирован: {web_url}")
        return web_url
    return clean_path


def select_categories_interactive(db) -> List[Category]:
    """Интерактивный выбор категорий: принимает номера категорий (например '1, 4')."""
    from backend.utils.category_parser import parse_category_ids

    categories = db.query(Category).order_by(Category.id.asc()).all()
    if not categories:
        init_db()
        categories = db.query(Category).order_by(Category.id.asc()).all()

    cats_dict = {c.id: c for c in categories}
    all_movies = db.query(Movie).all()

    # Считаем количество фильмов в каждой категории
    counts = {}
    for m in all_movies:
        for cid in m.parsed_category_ids:
            counts[cid] = counts.get(cid, 0) + 1

    print("\n--- ВЫБОР КАТЕГОРИЙ (укажите ID через запятую, например '1, 4') ---")
    for cat in categories:
        count = counts.get(cat.id, 0)
        icon_str = f" [иконка: {cat.icon_path}]" if cat.icon_path else ""
        print(f"  {cat.id}) {cat.name} (slug: {cat.slug}) [фильмов: {count}]{icon_str}")
    print("  +) Создать новую категорию")

    while True:
        raw_choice = input("\nВведите ID категорий через запятую (например '1, 4') [1]: ").strip() or "1"
        if raw_choice in ("+", "new", "n", "создать"):
            cat_name = prompt_non_empty("Название новой категории (например, 'Боевики')")
            from backend.routes.movies import get_or_create_category
            icon_in = input("URL/путь иконки (Enter для дефолтной): ").strip() or None
            new_cat, created = get_or_create_category(db, cat_name, icon_path=icon_in)
            if created:
                print(f"  [+] Создана категория: '{new_cat.name}' (ID: {new_cat.id})")
            else:
                print(f"  [!] Категория '{new_cat.name}' уже существовала в базе (ID: {new_cat.id})")
            return [new_cat]

        ids = parse_category_ids(raw_choice)
        selected = [cats_dict[cid] for cid in ids if cid in cats_dict]
        if selected:
            cat_titles = ", ".join(c.name for c in selected)
            print(f"  [OK] Закреплено категорий: {len(selected)} ({cat_titles})")
            return selected

        print("  [!] Не удалось распознать указанные ID. Повторите ввод.")


def interactive_add_movie():
    """Пошаговый мастер добавления фильма."""
    init_db()
    db = SessionLocal()
    try:
        print("\n" + "=" * 70)
        print("         МАСТЕР ДОБАВЛЕНИЯ НОВОГО ФИЛЬМА В КИНОХОСТИНГ")
        print("=" * 70)

        # ----------------------------------------------------------------------
        # ШАГ 1. Генерация PNR
        # ----------------------------------------------------------------------
        print("\n[Шаг 1/6] ГЕНЕРАЦИЯ УНИКАЛЬНОГО PNR")
        for _ in range(100):
            auto_pnr = generate_pnr(PNR_LENGTH)
            if not db.query(Movie.id).filter(Movie.pnr == auto_pnr).first():
                break

        print(f"Сгенерирован уникальный PNR: \033[1;32m{auto_pnr}\033[0m")
        pnr_choice = input(
            f"Использовать этот PNR? (Enter для '{auto_pnr}' или введите свой): "
        ).strip().upper()

        if not pnr_choice:
            pnr = auto_pnr
        else:
            if not is_valid_pnr(pnr_choice):
                print(f"  [X] Ошибка: PNR должен состоять ровно из 6 символов ({PNR_ALPHABET})")
                return
            if db.query(Movie.id).filter(Movie.pnr == pnr_choice).first():
                print(f"  [X] Ошибка: фильм с PNR '{pnr_choice}' уже существует в БД!")
                return
            pnr = pnr_choice

        print(f"  [OK] Закреплен PNR: \033[1;32m{pnr}\033[0m")

        # ----------------------------------------------------------------------
        # ШАГ 2. Выбор исходного видеофайла
        # ----------------------------------------------------------------------
        print("\n[Шаг 2/6] ВЫБОР ИСХОДНОГО ВИДЕОФАЙЛА")
        while True:
            raw_video_path = input("Укажите путь к видеофайлу (или перетащите файл сюда): ").strip()
            clean_vpath = clean_input_path(raw_video_path)
            source_video = Path(clean_vpath).expanduser().resolve()

            if not clean_vpath:
                print("  [!] Путь не может быть пустым.")
                continue
            if not source_video.is_file():
                print(f"  [X] Файл не найден: {source_video}")
                retry = input("  Попробовать снова? (y/n) [y]: ").strip().lower()
                if retry in ("n", "no", "н", "нет"):
                    print("  Отмена добавления фильма.")
                    return
                continue
            break

        # ----------------------------------------------------------------------
        # ШАГ 3. Автоматический парсинг метаданных видео
        # ----------------------------------------------------------------------
        print("\n[Шаг 3/6] АВТОМАТИЧЕСКИЙ ПАРСИНГ МЕТАДАННЫХ ВИДЕО")
        try:
            meta = extract_video_metadata(source_video)
            print(f"  [+] Видео успешно распознано (движок: {meta['backend']}):")
            print(f"      - Разрешение кадра: {meta['width']}x{meta['height']}")
            print(f"      - Качество:         \033[1;33m{meta['quality_label']}\033[0m")
            print(f"      - Длительность:     \033[1;32m{meta['duration_formatted']}\033[0m ({meta['duration_seconds']} сек)")
            print(f"      - Размер файла:     {meta['file_size_bytes'] / (1024*1024):.1f} МБ")
            duration = meta["duration_formatted"]
            quality = meta["quality_label"]
        except Exception as e:
            print(f"  [!] Предупреждение парсера: {e}")
            print("  Ввод параметров вручную:")
            duration = prompt_non_empty("Длительность (например, '2 ч 15 мин' или '45 мин')", default="120 мин")
            quality = prompt_non_empty("Качество (например, '1080p Full HD', '720p HD', '4K')", default="1080p Full HD")

        duration = normalize_duration_str(duration)
        quality = normalize_quality_str(quality)

        # ----------------------------------------------------------------------
        # ШАГ 4. Перемещение и переименование видеофайла в media/video/<PNR>.mp4
        # ----------------------------------------------------------------------
        print(f"\n[Шаг 4/6] ПЕРЕМЕЩЕНИЕ ВИДЕОФАЙЛА В <PNR>.mp4")
        VIDEO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        dest_video = VIDEO_STORAGE_DIR / f"{pnr}.mp4"

        if source_video.resolve() != dest_video.resolve():
            print(f"  Перемещение: {source_video.name} -> media/video/{pnr}.mp4 ...")
            try:
                shutil.move(str(source_video), str(dest_video))
                print(f"  [OK] Файл успешно перемещен в: {dest_video}")
            except Exception as e:
                print(f"  [!] Ошибка перемещения ({e}). Выполняем копирование...")
                shutil.copy2(str(source_video), str(dest_video))
                print(f"  [OK] Файл успешно скопирован в: {dest_video}")
        else:
            print(f"  [OK] Файл уже находится в целевой директории: {dest_video}")

        movie_page_url = f"/movie/video/{pnr}.mp4"

        # ----------------------------------------------------------------------
        # ШАГ 5. Ручной ввод оставшихся данных (название, описание, баннеры, категория, слайдер)
        # ----------------------------------------------------------------------
        print("\n[Шаг 5/6] РУЧНОЙ ВВОД ОСТАВШИХСЯ ДАННЫХ")
        # Предлагаем имя файла без расширения как подсказку для названия
        default_title = source_video.stem.replace(".", " ").replace("_", " ").title()
        title = prompt_non_empty("Название фильма (title)", default=default_title)
        description = prompt_non_empty("Описание фильма (description)")

        print("\nМедиафайлы оформления (постер и промо-баннеры):")
        raw_poster = prompt_non_empty(
            "Путь/URL постера (~2:3, верт.)",
            default="/images/error_items/error_items-img/bochflix-test-img-2.jpg",
        )
        poster_url = process_media_file(raw_poster, "posters", pnr, "poster")

        raw_desktop = prompt_non_empty(
            "Путь/URL баннера для Desktop 16:9",
            default="/images/error_items/error_items-img/bochflix-test-img.png",
        )
        banner_desktop_url = process_media_file(raw_desktop, "banners", pnr, "desktop")

        raw_mobile = prompt_non_empty(
            "Путь/URL баннера для Mobile 1.2:1 (~6:5)",
            default="/images/error_items/error_items-img/bochflix-test-img-3.jpg",
        )
        banner_mobile_url = process_media_file(raw_mobile, "banners", pnr, "mobile")

        # Выбор категорий (Many-to-Many)
        selected_categories = select_categories_interactive(db)
        category_ids = [c.id for c in selected_categories]
        category_names = ", ".join(c.name for c in selected_categories)
        primary_cat_id = category_ids[0] if category_ids else None

        # Флаг показа в главном промо-слайдере
        hero_choice = input("\nПоказывать в главном промо-слайдере (is_hero_banner)? (y/n) [n]: ").strip().lower()
        is_hero_banner = hero_choice in ("y", "yes", "д", "да", "1", "+")

        # Флаг 'Новое и популярное'
        has_new_pop = any(c.slug == "new-popular" for c in selected_categories)
        if not has_new_pop:
            pop_choice = input("Показывать в блоке 'Новое и популярное' (is_popular)? (y/n) [n]: ").strip().lower()
            is_popular = pop_choice in ("y", "yes", "д", "да", "1", "+")
        else:
            is_popular = True

        # Опциональные поля
        rating_input = input("\nРейтинг фильма (например, 8.5) [Enter для пропуска]: ").strip()
        rating = float(rating_input) if rating_input else None

        logo_url = input("URL логотипа [Enter для пропуска]: ").strip() or None
        trailer_url = input("URL трейлера [Enter для пропуска]: ").strip() or None

        # ----------------------------------------------------------------------
        # ШАГ 6. Предпоказ и сохранение в БД
        # ----------------------------------------------------------------------
        print("\n" + "=" * 74)
        print("                  ПРЕДПРОСМОТР КАРТОЧКИ ФИЛЬМА")
        print("=" * 74)
        print(f" PNR:                     \033[1;32m{pnr}\033[0m")
        print(f" Название:                \033[1m{title}\033[0m")
        print(f" Категории (Many-to-Many): \033[1;34m{category_names}\033[0m (IDs: {category_ids})")
        print(f" В промо-слайдере:        \033[1m{'ДА (is_hero_banner = True)' if is_hero_banner else 'НЕТ'}\033[0m")
        print(f" 'Новое и популярное':    \033[1m{'ДА (is_popular = True)' if is_popular else 'НЕТ'}\033[0m")
        print(f" Длительность:            \033[1;32m{duration}\033[0m")
        print(f" Качество/Разрешение:     \033[1;33m{quality}\033[0m")
        print(f" Описание:                {description}")
        print("-" * 74)
        print(f" Видеофайл (Nginx):       {movie_page_url}  (media/video/{pnr}.mp4)")
        print(f" Постер (2:3):            {poster_url}")
        print(f" Баннер Desktop (16:9):   {banner_desktop_url}")
        print(f" Баннер Mobile (1.2:1):   {banner_mobile_url}")
        print("-" * 74)
        print(f" Рейтинг:                 {rating if rating is not None else 'NULL'}")
        print("=" * 74)

        confirm = input("\nСохранить фильм в БД? (y/n) [y]: ").strip().lower()
        if confirm in ("y", "yes", "д", "да", ""):
            category_ids_str = ",".join(str(c.id) for c in selected_categories)
            new_movie = Movie(
                pnr=pnr,
                title=title,
                description=description,
                duration=duration,
                quality=quality,
                poster_url=poster_url,
                banner=banner_desktop_url,
                mobile_poster=banner_mobile_url,
                banner_desktop_url=banner_desktop_url,
                banner_mobile_url=banner_mobile_url,
                movie_page_url=movie_page_url,
                category_ids=category_ids_str,
                is_hero_banner=is_hero_banner,
                is_new_and_popular=is_popular,
                is_new_popular=is_popular,
                is_popular=is_popular,
                rating=rating,
                logo_url=logo_url,
                trailer=trailer_url,
                trailer_url=trailer_url,
            )
            db.add(new_movie)
            db.commit()
            db.refresh(new_movie)
            print(f"\n\033[1;32m[+] УСПЕШНО!\033[0m Фильм '{title}' сохранен в базу с PNR: \033[1;32m{new_movie.pnr}\033[0m!\n")
        else:
            print("\n[-] Сохранение отменено. Запись НЕ была добавлена в базу данных.\n")

    finally:
        db.close()


def list_movies():
    """Выводит список всех фильмов из базы данных с категориями и статусом промо-слайдера."""
    init_db()
    db = SessionLocal()
    try:
        movies = db.query(Movie).order_by(Movie.id.asc()).all()
        if not movies:
            print("\n[!] База данных пуста. Фильмы еще не добавлены.")
            return

        cats_lookup = {c.id: c.name for c in db.query(Category).all()}

        print(f"\nВсего фильмов в БД: {len(movies)}")
        print("-" * 115)
        print(f"{'ID':<4} | {'PNR':<8} | {'КАТЕГОРИИ':<24} | {'СЛАЙДЕР':<8} | {'ПОПУЛЯР':<8} | {'КАЧЕСТВО':<15} | {'НАЗВАНИЕ'}")
        print("-" * 115)
        for m in movies:
            cat_ids = m.parsed_category_ids
            cats = ", ".join(cats_lookup[cid] for cid in cat_ids if cid in cats_lookup) if cat_ids else "— БЕЗ КАТ. —"
            hero = "ДА" if m.is_hero_banner else "нет"
            pop = "ДА" if m.is_new_popular else "нет"
            print(f"{m.id:<4} | {m.pnr:<8} | {cats[:22]:<24} | {hero:<8} | {pop:<8} | {m.quality[:13]:<15} | {m.title}")
        print("-" * 115 + "\n")
    finally:
        db.close()


def list_categories():
    """Выводит список всех категорий и число фильмов в них."""
    init_db()
    db = SessionLocal()
    try:
        categories = db.query(Category).order_by(Category.id.asc()).all()
        movies = db.query(Movie).all()

        counts = {}
        for m in movies:
            for cid in m.parsed_category_ids:
                counts[cid] = counts.get(cid, 0) + 1

        print(f"\nВсего категорий: {len(categories)}")
        print("-" * 55)
        print(f"{'ID':<4} | {'НАЗВАНИЕ':<20} | {'SLUG':<16} | {'ФИЛЬМОВ'}")
        print("-" * 55)
        for c in categories:
            cnt = counts.get(c.id, 0)
            print(f"{c.id:<4} | {c.name[:18]:<20} | {(c.slug or '')[:14]:<16} | {cnt}")
        print("-" * 55 + "\n")
    finally:
        db.close()


def show_movie(pnr: str):
    """Показывает подробные данные одного фильма по PNR."""
    init_db()
    db = SessionLocal()
    try:
        clean_pnr = pnr.strip().upper()
        movie = db.query(Movie).filter(Movie.pnr == clean_pnr).first()
        if not movie:
            print(f"\n[X] Фильм с PNR '{clean_pnr}' не найден в БД.\n")
            return

        print("\n" + "=" * 70)
        print(f" ДЕТАЛИ ФИЛЬМА [{movie.pnr}] — {movie.title}")
        print("=" * 70)
        for k, v in movie.to_dict().items():
            print(f" {k:<20}: {v}")
        print("=" * 70 + "\n")
    finally:
        db.close()


def delete_movie_by_pnr(pnr: str):
    """Удаляет фильм из базы данных по PNR с подтверждением."""
    init_db()
    db = SessionLocal()
    try:
        clean_pnr = pnr.strip().upper()
        movie = db.query(Movie).filter(Movie.pnr == clean_pnr).first()
        if not movie:
            print(f"\n[X] Фильм с PNR '{clean_pnr}' не найден в БД.\n")
            return

        confirm = input(f"Удалить фильм '{movie.title}' (PNR: {clean_pnr})? (y/n): ").strip().lower()
        if confirm in ("y", "yes", "д", "да"):
            db.delete(movie)
            db.commit()
            print(f"\n[+] Фильм '{movie.title}' (PNR: {clean_pnr}) успешно удален из базы.\n")
        else:
            print("\n[-] Удаление отменено.\n")
    finally:
        db.close()


def main_interactive_menu():
    """Главное интерактивное меню."""
    print_banner()
    while True:
        print("Выберите действие:")
        print("  1) Добавить новый фильм (пошаговый мастер: PNR -> видео -> автопарсинг -> перемещение -> метаданные)")
        print("  2) Показать список всех фильмов в БД")
        print("  3) Показать список категорий")
        print("  4) Просмотреть карточку фильма по PNR")
        print("  5) Удалить фильм по PNR")
        print("  6) Инициализировать / проверить таблицы БД")
        print("  0) Выход")

        try:
            choice = input("\nВаш выбор: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            break

        if choice == "1":
            interactive_add_movie()
        elif choice == "2":
            list_movies()
        elif choice == "3":
            list_categories()
        elif choice == "4":
            pnr = input("Введите 6-значный PNR фильма: ").strip()
            if pnr:
                show_movie(pnr)
        elif choice == "5":
            pnr = input("Введите PNR фильма для удаления: ").strip()
            if pnr:
                delete_movie_by_pnr(pnr)
        elif choice == "6":
            init_db()
            print("\n[+] Таблицы базы данных успешно проверены/инициализированы.\n")
        elif choice in ("0", "q", "exit"):
            print("Работа завершена.")
            break
        else:
            print("  [!] Некорректный пункт меню. Повторите ввод.")


def main():
    parser = argparse.ArgumentParser(
        description="CLI-утилита для управления и наполнения базы данных кинохостинга Bochflix"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("add", help="Интерактивно добавить фильм (с автопарсингом видео)")
    subparsers.add_parser("list", help="Показать все фильмы в БД")
    subparsers.add_parser("categories", help="Показать все категории")
    subparsers.add_parser("init", help="Инициализировать таблицы БД и выполнить миграцию")

    show_parser = subparsers.add_parser("show", help="Показать фильм по PNR")
    show_parser.add_argument("pnr", type=str, help="6-значный PNR фильма")

    delete_parser = subparsers.add_parser("delete", help="Удалить фильм по PNR")
    delete_parser.add_argument("pnr", type=str, help="6-значный PNR фильма")

    args = parser.parse_args()

    if args.command == "add":
        interactive_add_movie()
    elif args.command == "list":
        list_movies()
    elif args.command == "categories":
        list_categories()
    elif args.command == "init":
        init_db()
        print("[+] База данных успешно инициализирована.")
    elif args.command == "show":
        show_movie(args.pnr)
    elif args.command == "delete":
        delete_movie_by_pnr(args.pnr)
    else:
        main_interactive_menu()


if __name__ == "__main__":
    main()
