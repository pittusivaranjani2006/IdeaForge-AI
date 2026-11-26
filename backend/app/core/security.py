"""
Security utilities: password hashing and JWT token management.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from app.core.config import get_settings

settings = get_settings()

# bcrypt with 12 rounds — good balance of security vs. performance
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
_MAX_PASSWORD_BYTES = 72
_RESERVED_JWT_CLAIMS = frozenset({"sub", "exp", "iat", "nbf"})
_DUMMY_PASSWORD = "IdeaForge-Dummy-Password-1!"
_DUMMY_HASH = _pwd_context.hash(_DUMMY_PASSWORD)


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return bcrypt hash of the given plaintext password."""
    if len(plain.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise ValueError("password must be at most 72 bytes")
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored hash."""
    if len(plain.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError, UnknownHashError):
        return False


def verify_dummy_password(plain: str) -> bool:
    """Verify a password against a fixed hash to equalize login timing."""
    return verify_password(plain, _DUMMY_HASH)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """
    Create a signed JWT.

    Args:
        subject: The user ID (stored as `sub` claim).
        expires_delta: Override the default expiry.
        extra_claims: Additional claims merged into the payload.

    Returns:
        A signed JWT string.
    """
    subject = str(subject)
    if not subject:
        raise ValueError("subject must not be empty")

    reserved = _RESERVED_JWT_CLAIMS.intersection(extra_claims or {})
    if reserved:
        raise ValueError(
            "extra_claims must not contain reserved claims: "
            + ", ".join(sorted(reserved))
        )

    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire, "iat": now}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Optional[str]:
    """
    Decode and validate a JWT.

    Returns:
        The `sub` claim (user ID) if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require_exp": True, "require_iat": True, "require_sub": True},
        )
    except (JWTError, ValueError, TypeError):
        return None

    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    if not sub.isdigit() or int(sub) <= 0:
        return None
    return sub
