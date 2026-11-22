"""Shared SQLAlchemy registry; importing this does not connect to the database."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
