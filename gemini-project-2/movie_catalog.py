"""Терминальный каталог Bochflix. Запуск: python movie_catalog.py [--project ПУТЬ]."""

import argparse
import shutil
import sqlite3
import sys
from contextlib import ExitStack, closing
from pathlib import Path


def find_backend(project):
    folders = [project] if project else [
        Path(__file__).resolve().parent, Path.cwd(), Path("C:/My_corseproject")
    ]
    for folder in folders:
        for root in (folder, folder / "gemini-project-2"):
            if (root / "data/cinema.db").is_file():
                return root.resolve()
    raise ValueError("База data/cinema.db не найдена. Укажите папку проекта через --project.")


def connect(root, mode):
    uri = (root / "data/cinema.db").as_uri() + "?mode=" + mode
    db = sqlite3.connect(uri, uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def ask_file(label, extensions):
    while True:
        raw = input(f"Путь до {label} ({', '.join(extensions)}): ").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
            raw = raw[1:-1]
        path = Path(raw).expanduser()
        if not path.is_file():
            print("Файл не найден. Проверьте путь.")
        elif path.suffix.lower() not in extensions:
            print("Неподдерживаемое расширение. Выберите другой файл.")
        elif not path.stat().st_size:
            print("Файл пуст. Выберите другой файл.")
        else:
            return path


def ask_text(label, default=""):
    while True:
        hint = f" [{default}]" if default else ""
        value = input(f"{label}{hint}: ").strip() or default
        if value:
            return value
        print("Введите значение.")


def category_list(db):
    return {str(c["id"]): c["name"] for c in db.execute(
        "SELECT id, name FROM categories ORDER BY id"
    )}


def select_categories(db):
    options = category_list(db)
    if not options:
        return ""
    print("Категории:", ", ".join(f"{key} — {name}" for key, name in options.items()))
    default = next((k for k, name in options.items() if name == "Фильмы"), next(iter(options)))
    while True:
        raw = ask_text("Номера категорий через запятую", default)
        ids = dict.fromkeys(part.strip() for part in raw.split(","))
        if ids.keys() <= options.keys():
            return ",".join(ids)
        print("Введите номера из списка.")


def save_movie(db, media, sources, details, generate_pnr):
    banner, poster, video = sources
    for _ in range(100):
        pnr = generate_pnr()
        paths = [
            Path("banners") / f"{pnr}_desktop{banner.suffix.lower()}",
            Path("posters") / f"{pnr}_poster{poster.suffix.lower()}",
            Path("video") / f"{pnr}{video.suffix.lower()}",
        ]
        if db.execute("SELECT 1 FROM movies WHERE pnr = ?", (pnr,)).fetchone():
            continue
        # Регистрируем только созданные нами файлы. Режим xb защищает от перезаписи.
        with ExitStack() as cleanup:
            try:
                for src, rel in zip(sources, paths):
                    dest = media / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with src.open("rb") as infile, dest.open("xb") as outfile:
                        cleanup.callback(dest.unlink, missing_ok=True)
                        shutil.copyfileobj(infile, outfile, 1024 * 1024)
            except FileExistsError:
                continue

            banner_url, poster_url, video_url = ["/media/" + p.as_posix() for p in paths]
            if video.suffix.lower() == ".mp4":
                video_url = "/movie/" + paths[2].as_posix()
            # Открываем транзакцию записи только после копирования большого видео.
            with db:
                db.execute("""
                    INSERT INTO movies (
                        pnr, title, description, duration, quality, category_ids,
                        banner, poster_url, mobile_poster, movie_page_url,
                        banner_desktop_url, banner_mobile_url, is_hero_banner,
                        is_new_and_popular, is_new_popular, is_popular, is_new
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)
                """, (pnr, *details, banner_url, poster_url, poster_url, video_url,
                      banner_url, poster_url))
            cleanup.pop_all()
            return pnr
    raise ValueError("Не удалось подобрать свободный код фильма.")


def add_movie(root):
    # Это автономные модули проекта. Импорт backend целиком запустил бы FastAPI.
    from pnr import generate_pnr
    from video_meta import extract_video_metadata

    images = (".jpg", ".jpeg", ".png", ".webp")
    banner = ask_file("баннера", images)
    poster = ask_file("постера", images)
    video = ask_file("видео", (".mp4", ".webm"))
    title = ask_text("Название фильма", video.stem)
    description = input("Описание (Enter — пропустить): ").strip()
    meta = extract_video_metadata(video)
    duration = ask_text("Длительность", meta["duration_formatted"] if meta["duration_seconds"] > 0 else "")
    quality = ask_text("Качество", meta["quality_label"] if meta["backend"] != "fallback" else "")
    with closing(connect(root, "rw")) as db:
        categories = select_categories(db)
        print("Копирование файлов…")
        pnr = save_movie(db, root / "media", (banner, poster, video),
                         (title, description, duration, quality, categories), generate_pnr)
    print(f"Добавлен фильм «{title}». Код PNR: {pnr}")


def search_movies(root):
    query = ask_text("Название, часть названия, ID или код PNR")
    with closing(connect(root, "ro")) as db:
        db.create_function("casefold", 1, str.casefold)
        categories = category_list(db)
        rows = db.execute("""
            SELECT * FROM movies WHERE instr(casefold(title), ?) > 0
                OR pnr = ? COLLATE NOCASE OR CAST(id AS TEXT) = ?
            ORDER BY casefold(title), id
        """, (query.casefold(), query, query))
        count = 0
        for row in rows:
            count += 1
            ids = (row["category_ids"] or "").split(",")
            names = ", ".join(categories.get(i.strip(), i.strip()) for i in ids if i.strip())
            print(f"\n{row['title']}  |  ID {row['id']}  |  PNR {row['pnr']}")
            print(f"Категории: {names or '—'}")
            for label, key in (
                ("Описание", "description"), ("Длительность", "duration"), ("Качество", "quality"),
                ("Год", "year"), ("Жанр", "genre"), ("Рейтинг", "rating"), ("Автор", "creator"),
                ("Баннер", "banner"), ("Постер", "poster_url"), ("Мобильный постер", "mobile_poster"),
                ("Видео", "movie_page_url"), ("Трейлер", "trailer"),
            ):
                if row[key] is not None and row[key] != "":
                    print(f"{label}: {row[key]}")
        print(f"\nНайдено фильмов: {count}." if count else "Фильмы не найдены.")


def main():
    parser = argparse.ArgumentParser(description="Добавление и поиск фильмов Bochflix")
    parser.add_argument("--project", type=Path, help="Папка проекта или gemini-project-2")
    root = find_backend(parser.parse_args().project)
    sys.path.insert(0, str(root / "backend/utils"))
    print(f"Каталог: {root}")
    while True:
        print("\n1 — Добавить фильм\n2 — Найти фильм\n0 — Выход")
        choice = input("Выбор: ").strip()
        try:
            if choice == "1":
                add_movie(root)
            elif choice == "2":
                search_movies(root)
            elif choice == "0":
                return
            else:
                print("Введите 1, 2 или 0.")
        except (OSError, sqlite3.Error, ValueError, ImportError) as exc:
            print(f"Не удалось выполнить операцию: {exc}")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nВыход.")
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
