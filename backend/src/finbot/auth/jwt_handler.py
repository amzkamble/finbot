"""JWT token creation and validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from finbot.config.settings import get_settings
from finbot.utils.exceptions import AuthenticationError
from finbot.utils.logger import get_logger

logger = get_logger(__name__)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token.

    Parameters
    ----------
    data : dict
        Payload to encode (must include ``sub``, ``role``).
    expires_delta : timedelta, optional
        Custom expiry. Falls back to ``settings.jwt_expiry_minutes``.

    Returns
    -------
    str
        Encoded JWT string.
    """
    settings = get_settings()
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_expiry_minutes)
    )
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Validate and decode a JWT token.

    Returns
    -------
    dict
        Decoded payload with ``sub``, ``role``, ``username``, etc.

    Raises
    ------
    AuthenticationError
        If the token is invalid, expired, or missing required claims.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise AuthenticationError("Invalid or expired token") from exc

    if "sub" not in payload or "role" not in payload:
        raise AuthenticationError("Token missing required claims")

    return payload
