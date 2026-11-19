from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.modules.posts import application
from app.modules.posts.schemas import PostResponse


router = APIRouter(prefix="/tags", tags=["Tags"])

@router.get("/", response_model=List[dict])
def get_all_tags(db: Session = Depends(get_db)):
    return application.get_all_tags(db)

@router.get("/{tag_slug}/posts", response_model=List[PostResponse])
def get_posts_by_tag(tag_slug: str, db: Session = Depends(get_db)):
    return application.get_posts_by_tag(db, tag_slug)
