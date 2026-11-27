"""Android catalogue backed by the same movie records as the main API."""
from typing import Literal
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Category, Movie

router = APIRouter(tags=["Android catalogue"])


def serialize(movie: Movie, request: Request, categories: dict) -> dict:
    def absolute(path: str | None) -> str:
        return urljoin(str(request.base_url), path or "") if path else ""

    names = [categories[c] for c in movie.parsed_category_ids if c in categories]
    return {
        "id": movie.id, "title": movie.title, "description": movie.description,
        "year": movie.year or 0, "genre": movie.genre or " · ".join(names),
        "duration": movie.duration, "rating": movie.rating or 0,
        "posterUrl": absolute(movie.poster_url), "videoUrl": absolute(movie.movie_page_url),
        "creator": movie.creator or "", "license": movie.license or "",
        "sourceUrl": movie.source_url or "",
    }


def category_names(db: Session) -> dict:
    return {category.id: category.name for category in db.query(Category).all()}


@router.get("/films")
def films(request: Request, db: Session = Depends(get_db),
          section: Literal["films", "series"] | None = None):
    categories = db.query(Category).all()
    names = {category.id: category.name for category in categories}
    series_id = next((category.id for category in categories if category.slug == "series"), None)
    movies = db.query(Movie).order_by(Movie.id)
    if section is not None:
        want_series = section == "series"
        movies = (movie for movie in movies if (series_id in movie.parsed_category_ids) == want_series)
    return [serialize(movie, request, names) for movie in movies]


@router.get("/films/{film_id}")
def film(film_id: int, request: Request, db: Session = Depends(get_db)):
    movie = db.get(Movie, film_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    return serialize(movie, request, category_names(db))
