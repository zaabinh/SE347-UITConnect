"""Environment configuration shared by the application and scripts."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, SecretStr, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_JWT_SECRET = "change-this-in-production"
PLACEHOLDER_JWT_SECRETS = {
    DEFAULT_JWT_SECRET,
    "change-me-in-prod",
    "change-me",
    "replace-with-a-long-random-secret",
    "generate-a-long-random-secret",
    "chuoi-random-dai",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        str_strip_whitespace=True,
        frozen=True,
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = Field(min_length=1, repr=False)
    frontend_url: HttpUrl
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(min_length=1)
    jwt_secret_key: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)
    upload_dir: str = Field(default="uploads", min_length=1)
    public_api_url: HttpUrl | None = None
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: HttpUrl = HttpUrl("http://127.0.0.1:8000/auth/google/callback")
    app_host: str = Field(default="0.0.0.0", min_length=1)
    app_port: int = Field(default=8000, ge=1, le=65535)
    port: int = Field(default=10000, ge=1, le=65535)
    run_db_setup_on_start: bool = False
    skip_db_upgrade: bool = False
    seed_admin_email: str = "admin@studentforum.dev"
    seed_admin_username: str = "admin"
    seed_admin_password: SecretStr = SecretStr("admin12345")
    seed_admin_full_name: str = "Administrator"
    mail_logo_example: str = ""

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        return {"prod": "production", "dev": "development"}.get(normalized, normalized)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        try:
            make_url(value)
        except Exception as exc:
            raise ValueError("DATABASE_URL must be a SQLAlchemy URL.") from exc
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        origins = value.split(",") if isinstance(value, str) else value
        parsed = [origin.strip() for origin in origins if origin.strip()]
        for origin in parsed:
            url = TypeAdapter(HttpUrl).validate_python(origin)
            if url.path not in {None, "/"} or url.query or url.fragment or url.username or url.password:
                raise ValueError("CORS_ALLOWED_ORIGINS must contain HTTP origins without paths or credentials.")
        return [origin.rstrip("/") for origin in parsed]

    @field_validator("public_api_url", mode="before")
    @classmethod
    def empty_public_api_url(cls, value: str | None) -> str | None:
        return None if value == "" else value

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_empty_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("JWT_SECRET_KEY must not be empty.")
        return value

    @model_validator(mode="after")
    def validate_production_secret(self) -> Self:
        secret = self.jwt_secret_key.get_secret_value().strip()
        if self.app_env == "production" and (
            secret.lower() in PLACEHOLDER_JWT_SECRETS or len(secret) < 32
        ):
            raise ValueError("Production requires a non-default JWT_SECRET_KEY of at least 32 characters.")
        return self


# Validate all settings before routers, database setup or startup side effects run.
settings = Settings()
