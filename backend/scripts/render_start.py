"""Render-compatible backend startup."""

from __future__ import annotations

import os

from app.core.config import settings


def run_database_setup() -> None:
    from scripts.setup_local_db import create_or_reset_tables, get_database_url, run_upgrade

    _ = get_database_url()
    create_or_reset_tables(reset=False)

    if not settings.skip_db_upgrade:
        run_upgrade()


def main() -> None:
    if settings.run_db_setup_on_start:
        run_database_setup()

    port = str(settings.port)
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
    )


if __name__ == "__main__":
    main()
