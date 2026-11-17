from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.modules.posts.models import Tag
from app.modules.posts.schemas import PostResponse


router = APIRouter(prefix="/tags", tags=["Tags"])

@router.get("/", response_model=List[dict])
def get_all_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug} for t in tags]

@router.get("/{tag_slug}/posts", response_model=List[PostResponse])
def get_posts_by_tag(tag_slug: str, db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.slug == tag_slug).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhãn dán này.")
    
    return tag.posts
