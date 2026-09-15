from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT helpers - never include password/hash
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    exp = now + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"iat": int(now.timestamp()), "exp": int(exp.timestamp())})
    # Ensure no sensitive fields leak
    to_encode.pop("password", None)
    to_encode.pop("password_hash", None)
    to_encode.pop("secret", None)
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_reset_token(email: str, expires_minutes: int = 15) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)
    to_encode = {"sub": email, "purpose": "password_reset", "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        raise ValueError(str(e)) from e
