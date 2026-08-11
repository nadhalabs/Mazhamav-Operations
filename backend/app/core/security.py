from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes), "iss": "mazha-mav-api", "aud": "mazha-mav-web"}, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"], issuer="mazha-mav-api", audience="mazha-mav-web")["sub"]
