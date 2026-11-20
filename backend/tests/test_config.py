import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_JWT_SECRET, PLACEHOLDER_JWT_SECRETS, Settings


@pytest.fixture
def config_env(monkeypatch):
    for name in list(os.environ):
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:3000")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")


def test_environment_overrides_dotenv(config_env, monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ACCESS_TOKEN_EXPIRE_MINUTES=15\nUNRELATED_VALUE=ignored\n")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " http://localhost:3000, https://ui.example.com/ , ")
    config = Settings(_env_file=env_file)
    assert config.access_token_expire_minutes == 30
    assert config.cors_allowed_origins == ["http://localhost:3000", "https://ui.example.com"]


@pytest.mark.parametrize("name", ["DATABASE_URL", "CORS_ALLOWED_ORIGINS"])
def test_required_configuration(config_env, monkeypatch, name):
    monkeypatch.delenv(name)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_frontend_url_has_local_default(config_env, monkeypatch):
    monkeypatch.delenv('FRONTEND_URL')
    assert str(Settings(_env_file=None).frontend_url).rstrip('/') == 'http://localhost:3000'


@pytest.mark.parametrize(("name", "value"), [
    ("DATABASE_URL", "raw-odbc-string"),
    ("FRONTEND_URL", "not-a-url"),
    ("CORS_ALLOWED_ORIGINS", ""),
    ("CORS_ALLOWED_ORIGINS", "*"),
    ("CORS_ALLOWED_ORIGINS", "https://ui.example.com/path"),
    ("ACCESS_TOKEN_EXPIRE_MINUTES", "0"),
    ("REFRESH_TOKEN_EXPIRE_DAYS", "-1"),
    ("APP_PORT", "65536"),
    ("PORT", "not-an-integer"),
    ("RUN_DB_SETUP_ON_START", "maybe"),
    ("JWT_SECRET_KEY", "   "),
    ("JWT_ALGORITHM", "none"),
    ("APP_ENV", "productoin"),
    ("UPLOAD_DIR", "   "),
])
def test_invalid_environment_values(config_env, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("secret", [None, "short", *sorted(PLACEHOLDER_JWT_SECRETS)])
def test_production_rejects_missing_default_and_weak_secrets(config_env, monkeypatch, secret):
    monkeypatch.setenv("APP_ENV", "production")
    if secret is not None:
        monkeypatch.setenv("JWT_SECRET_KEY", secret)
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(_env_file=None)


def test_development_can_use_default_secret(config_env):
    assert Settings(_env_file=None).jwt_secret_key.get_secret_value() == DEFAULT_JWT_SECRET


def test_production_accepts_custom_secret_and_redacts_secrets(config_env, monkeypatch):
    secret = "e63b84e876a9b70b95f28476eb5933f911f08ed2043439c6b"
    database_url = "mssql+pyodbc://user:private-password@db/forum"
    monkeypatch.setenv("APP_ENV", " PROD ")
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    monkeypatch.setenv("DATABASE_URL", database_url)
    config = Settings(_env_file=None)
    assert config.app_env == "production"
    assert config.jwt_secret_key.get_secret_value() == secret
    assert secret not in repr(config)
    assert database_url not in repr(config)
    monkeypatch.setenv("PORT", "invalid")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert secret not in str(error.value)
    assert database_url not in str(error.value)


@pytest.mark.parametrize("entrypoint", ["app.main", "app.__main__"])
def test_production_fails_before_startup_side_effects(config_env, monkeypatch, entrypoint):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET)
    monkeypatch.setenv("RUN_DB_SETUP_ON_START", "true")
    code = (
        "from unittest.mock import patch\n"
        "with patch('sqlalchemy.create_engine', side_effect=AssertionError('DB_TOUCHED')), "
        "patch('os.execvp', side_effect=AssertionError('SERVER_STARTED')):\n"
        f"    __import__({entrypoint!r})\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Production requires" in result.stderr
    assert "DB_TOUCHED" not in result.stderr
    assert "SERVER_STARTED" not in result.stderr
