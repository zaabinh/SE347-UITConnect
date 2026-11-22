"""One-command local database setup.

Default behavior is non-destructive:
- create the target SQL Server database if it does not exist
- run versioned Alembic migrations, never ORM create_all or raw upgrade SQL
"""

from __future__ import annotations

import argparse
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from scripts.db_schema import collation_name
from scripts.migration_policy import baseline_snapshot

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Setup the local StudentForum database.")
    parser.add_argument("--seed", action="store_true", help="Seed demo data after setup.")
    parser.add_argument("--wait", type=int, default=60, help="Seconds to wait for SQL Server to accept connections.")
    return parser.parse_args()


def get_database_url() -> str:
    return settings.database_url


def quote_sqlserver_identifier(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


def create_database_if_missing(database_url: str, wait_seconds: int) -> None:
    url = make_url(database_url)
    database_name = url.database
    if not database_name:
        raise RuntimeError("DATABASE_URL must include a database name.")

    master_url = url.set(database="master")
    deadline = time.monotonic() + max(wait_seconds, 0)
    last_error: Exception | None = None

    while True:
        engine = create_engine(master_url, pool_pre_ping=True, future=True, isolation_level="AUTOCOMMIT", hide_parameters=True)
        try:
            with engine.connect() as conn:
                if conn.execute(text("SELECT DB_ID(:database_name)"), {"database_name": database_name}).scalar_one() is None:
                    collation = collation_name(baseline_snapshot()['collation'])
                    conn.exec_driver_sql(f"CREATE DATABASE {quote_sqlserver_identifier(database_name)} COLLATE {collation}")
            print(f"Database ready: {database_name}")
            return
        except OperationalError as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                break
            time.sleep(2)
        finally:
            engine.dispose()

    raise RuntimeError(f"SQL Server is not ready after {wait_seconds}s.") from last_error


def run_upgrade() -> None:
    from scripts.upgrade_db import main as upgrade_main

    upgrade_main()


def run_seed() -> None:
    from scripts.seed import run_seed

    run_seed()


def main() -> None:
    args = parse_args()
    database_url = get_database_url()

    create_database_if_missing(database_url, args.wait)
    run_upgrade()

    if args.seed:
        run_seed()

    print("Local database setup completed.")


if __name__ == "__main__":
    main()
