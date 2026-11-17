"""ASGI entrypoint shared by local development, Docker and Render."""

from app.factory import create_app

app = create_app()
