"""Server-side accounts: salted password hashes and encrypted profile fields."""
import hashlib
import hmac
import os
import secrets
import time
from functools import lru_cache

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import AuthSession, User

router = APIRouter(prefix="/auth", tags=["Accounts"])
bearer = HTTPBearer()
ITERATIONS = 600_000


@lru_cache
def profile_key() -> bytes:
    configured = os.environ.get("PROFILE_ENCRYPTION_KEY")
    if configured:
        return configured.encode("ascii")
    path = settings.DB_PATH.parent / "profile.key"
    try:
        with path.open("xb") as output:
            output.write(Fernet.generate_key())
    except FileExistsError:
        pass
    return path.read_bytes()


def email_digest(email: str) -> str:
    return hmac.new(profile_key(), email.strip().lower().encode(), hashlib.sha256).hexdigest()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)), stored)
    except ValueError:
        return False


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=256)


class Registration(Login):
    name: str = Field(min_length=1, max_length=100)


def profile(user: User) -> dict:
    cipher = Fernet(profile_key())
    return {"id": user.id, "name": cipher.decrypt(user.name_encrypted.encode()).decode(),
            "email": cipher.decrypt(user.email_encrypted.encode()).decode()}


@router.post("/register", status_code=201)
def register(data: Registration, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if "@" not in email or not data.name.strip():
        raise HTTPException(422, "Проверьте имя и электронную почту")
    cipher = Fernet(profile_key())
    user = User(email_digest=email_digest(email), email_encrypted=cipher.encrypt(email.encode()).decode(),
                name_encrypted=cipher.encrypt(data.name.strip().encode()).decode(),
                password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Этот адрес уже зарегистрирован")
    return {"status": "created"}


@router.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email_digest=email_digest(data.email)).first()
    # Perform password derivation even for unknown addresses.
    stored = user.password_hash if user else f"pbkdf2_sha256${ITERATIONS}${'00' * 16}${'00' * 32}"
    valid = verify_password(data.password, stored)
    if not user or not valid:
        raise HTTPException(401, "Аккаунт не найден или пароль неверный")
    token = secrets.token_urlsafe(32)
    db.query(AuthSession).filter(AuthSession.expires_at <= int(time.time())).delete()
    db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                       expires_at=int(time.time()) + 86400))
    db.commit()
    return {"token": token, "user": profile(user)}


def current_session(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    session = db.get(AuthSession, hashlib.sha256(credentials.credentials.encode()).hexdigest())
    if not session or session.expires_at <= int(time.time()):
        raise HTTPException(401, "Войдите в аккаунт")
    return session


@router.get("/me")
def me(session: AuthSession = Depends(current_session), db: Session = Depends(get_db)):
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Войдите в аккаунт")
    return profile(user)


@router.post("/logout", status_code=204)
def logout(session: AuthSession = Depends(current_session), db: Session = Depends(get_db)):
    db.delete(session)
    db.commit()
