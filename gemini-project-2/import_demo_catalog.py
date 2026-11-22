"""One-time, repeatable import of the original Android demo catalogue."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path(r"C:\BochkinoVideoServer\catalog.json")

with SOURCE.open(encoding="utf-8") as stream:
    demos = json.load(stream)

with sqlite3.connect(ROOT / "data" / "cinema.db") as db:
    columns = {row[1] for row in db.execute("PRAGMA table_info(movies)")}
    for name, kind in (("year", "INTEGER"), ("genre", "VARCHAR(255)"),
                       ("creator", "VARCHAR(255)"), ("license", "VARCHAR(255)"),
                       ("source_url", "VARCHAR(500)")):
        if name not in columns:
            db.execute(f"ALTER TABLE movies ADD COLUMN {name} {kind}")
    for demo, pnr in zip(demos, ("RVR001", "RVR002")):
        db.execute("""INSERT INTO movies
            (pnr, title, description, duration, quality, poster_url, banner, mobile_poster,
             movie_page_url, is_hero_banner, is_new_and_popular, is_new_popular, is_popular,
             is_new, category_ids, rating, year, genre, creator, license, source_url)
            SELECT ?, ?, ?, ?, ?, ?, '', '', ?, 0, 0, 0, 0, 0, '', ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM movies WHERE pnr = ?)""",
            (pnr, demo['title'], demo['description'], demo['duration'], 'SD',
             '/media/posters/' + demo['posterUrl'] + '.jpg',
             '/media/video/' + demo['videoUrl'] + '.webm', demo['rating'], demo['year'],
             demo['genre'], demo['creator'], demo['license'], demo['sourceUrl'], pnr))
