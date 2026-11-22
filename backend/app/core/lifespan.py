"""Manage resources once per server worker; schema changes run separately."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        Path(app.state.settings.upload_dir).mkdir(parents=True, exist_ok=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Student Forum API started")
        yield
    finally:
        engine.dispose()
        logger.info("Student Forum API resources released")
