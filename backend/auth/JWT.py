from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError , jwt

from .config import auth_settings

# Token type literal used in the payload to distinguish access vs refresh tokens
TokenType = Literal["access", "refresh"]


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": subject,          # subject (username or user ID)
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, auth_settings.SECRET_KEY, algorithm=auth_settings.ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject,
        token_type="access",
        expires_delta=timedelta(minutes=auth_settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        token_type="refresh",
        expires_delta=timedelta(days=auth_settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT.

    Raises:
        JWTError: if the token is invalid, expired, or tampered with.
    """
    return jwt.decode(
        token,
        auth_settings.SECRET_KEY,
        algorithms=[auth_settings.ALGORITHM],
    )