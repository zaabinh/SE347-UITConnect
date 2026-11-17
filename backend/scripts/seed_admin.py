from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.users.models import User
from app.core.security import hash_password


def create_admin() -> User:
    db: Session = SessionLocal()
    admin_email = settings.seed_admin_email.strip().lower()
    admin_username = settings.seed_admin_username.strip().lower()
    admin_password = settings.seed_admin_password.get_secret_value()
    admin_full_name = settings.seed_admin_full_name.strip()

    try:
        existing_admin = db.query(User).filter(User.role.ilike("admin")).first()
        if existing_admin:
            return existing_admin

        admin = User(
            email=admin_email,
            username=admin_username,
            full_name=admin_full_name,
            password_hash=hash_password(admin_password),
            major="Computer Science",
            academic_year="K18",
            career_goal="Platform Admin",
            interest_tags="moderation,platform,operations",
            role="admin",
            status="active",
            provider="local",
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    finally:
        db.close()


if __name__ == "__main__":
    account = create_admin()
    print(f"Admin ready: {account.email}")
