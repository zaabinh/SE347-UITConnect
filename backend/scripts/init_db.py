"""Initialize database tables"""
from app.db.base import Base
from app.db.session import engine
from app.modules import AuthSession, Bookmark, Comment, Follow, Post, User

# Drop existing tables and recreate (for idempotency)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✅ Database tables recreated successfully!")
