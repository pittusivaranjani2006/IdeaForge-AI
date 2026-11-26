"""
Application configuration loaded from environment variables.
Uses pydantic-settings for validation and type safety.
"""
import ipaddress
import re
from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})
_ENVIRONMENT_ALIASES = {"dev": "development", "prod": "production"}
_HOSTNAME_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
)
_PLACEHOLDER_SECRETS = frozenset({
    "CHANGE_THIS_IN_PRODUCTION",
    "CHANGE-ME-TO-A-LONG-RANDOM-STRING-AT-LEAST-32-CHARS",
    "CHANGEME",
    "SECRET",
    "YOUR_SECRET_KEY",
})
_SUPPORTED_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})


def _validate_production_origin(origin: str) -> None:
    if origin != origin.strip() or any(char.isspace() for char in origin):
        raise ValueError("production CORS origins must be well-formed HTTPS URLs")
    parsed = urlparse(origin)
    if parsed.scheme.lower() != "https":
        raise ValueError("production CORS origins must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("production CORS origins must not contain credentials")
    if (
        "?" in origin
        or "#" in origin
        or ";" in origin
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.params
    ):
        raise ValueError(
            "production CORS origins must not contain path, query, or fragment"
        )
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("production CORS origins must be well-formed HTTPS URLs")
    host = parsed.hostname.lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    mapped_address = getattr(address, "ipv4_mapped", None)
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or (address is not None and address.is_loopback)
        or (mapped_address is not None and mapped_address.is_loopback)
    ):
        raise ValueError("production CORS origins must not use loopback hosts")
    if address is None:
        if len(host) > 253 or not _HOSTNAME_PATTERN.fullmatch(host):
            raise ValueError("production CORS origins must be well-formed HTTPS URLs")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(
            "production CORS origins must be well-formed HTTPS URLs"
        ) from exc
    if port is not None and port < 1:
        raise ValueError("production CORS origins must be well-formed HTTPS URLs")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def __init__(self, **values):
        try:
            super().__init__(**values)
        except ValidationError as exc:
            sanitized = ValidationError.from_exception_data(
                exc.title,
                exc.errors(),
                hide_input=True,
            )
            raise sanitized from None

    # ── Database ──────────────────────────────────────────────
    database_url: str

    # ── JWT ───────────────────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── AI Provider ───────────────────────────────────────────
    openai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"

    # ── CORS ──────────────────────────────────────────────────
    allowed_origins: str = (
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000"
    )

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("DATABASE_URL must not be empty")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("SECRET_KEY must not be empty")
        if v.upper() in _PLACEHOLDER_SECRETS:
            raise ValueError("SECRET_KEY must not be a placeholder")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        if len(set(v)) < 8:
            raise ValueError("SECRET_KEY must have sufficient entropy")
        return v

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in _ALLOWED_ALGORITHMS:
            raise ValueError("ALGORITHM must be one of HS256, HS384, or HS512")
        return v

    @field_validator("access_token_expire_minutes")
    @classmethod
    def validate_expiration(cls, v: int) -> int:
        if v < 1 or v > 1440:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 1440")
        return v

    # ── Rate Limiting ─────────────────────────────────────────
    rate_limit_per_minute: int = 30
    ai_rate_limit_per_minute: int = 10

    # ── App ───────────────────────────────────────────────────
    app_env: str = "development"
    app_version: str = "1.0.0"

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        normalized = v.strip().lower()
        normalized = _ENVIRONMENT_ALIASES.get(normalized, normalized)
        if normalized not in _SUPPORTED_ENVIRONMENTS:
            raise ValueError(
                "APP_ENV must be one of development, test, staging, production"
            )
        return normalized

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_url(self) -> Optional[str]:
        return "/docs" if self.is_development else None

    @property
    def redoc_url(self) -> Optional[str]:
        return "/redoc" if self.is_development else None

    @model_validator(mode="after")
    def validate_environment_configuration(self) -> "Settings":
        if not self.is_production:
            return self
        if "allowed_origins" not in self.model_fields_set:
            raise ValueError(
                "ALLOWED_ORIGINS must be explicitly configured in production"
            )
        if not self.cors_origins:
            raise ValueError(
                "ALLOWED_ORIGINS must include at least one origin in production"
            )
        for origin in self.cors_origins:
            _validate_production_origin(origin)
        if "database_url" not in self.model_fields_set:
            raise ValueError("DATABASE_URL must be explicitly configured in production")
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
