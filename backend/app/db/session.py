from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.exceptions import ConfigurationError


def normalize_database_url(database_url: str) -> str:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise ConfigurationError("DATABASE_URL must be a SQLAlchemy URL, not a raw ODBC connection string.") from exc

    if url.drivername != "mssql+pyodbc":
        return database_url

    query = dict(url.query)
    query.setdefault("driver", "ODBC Driver 18 for SQL Server")
    driver_name = query["driver"].strip("{}")

    try:
        import pyodbc
    except ImportError as exc:
        raise ConfigurationError("pyodbc is not installed. Install backend requirements or deploy with the backend Dockerfile.") from exc

    installed_drivers = set(pyodbc.drivers())
    if driver_name not in installed_drivers:
        available = ", ".join(sorted(installed_drivers)) or "none"
        raise ConfigurationError(
            f"ODBC driver '{driver_name}' is not installed. "
            f"Available ODBC drivers: {available}. "
            "On Render, deploy this backend as a Docker service using backend/Dockerfile."
        )

    return url.set(query=query).render_as_string(hide_password=False)


DATABASE_URL = normalize_database_url(settings.database_url)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    hide_parameters=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
