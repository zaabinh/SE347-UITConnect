from sqlalchemy import or_

from app.db.repository import Repository
from app.modules.auth.models import AuthSession, EmailVerificationToken, PasswordResetToken
from app.modules.users.models import User


class AuthRepository(Repository):
    def find_identifier(self, identifier):
        return self.query(User).filter(or_(User.email == identifier, User.username == identifier)).first()

    def registration_conflict(self, email, username):
        return self.query(User).filter(or_(User.email == email, User.username == username)).first()

    def find_email(self, email):
        return self.query(User).filter(User.email == email).first()

    def find_user(self, user_id):
        return self.query(User).filter(User.id == user_id).first()

    def username_taken(self, username, user_id):
        return self.query(User).filter(User.username == username, User.id != user_id).first() is not None

    def find_session(self, token):
        return self.query(AuthSession).filter(AuthSession.refresh_token == token).first()

    def find_reset_token(self, token):
        return self.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()

    def delete_user_sessions(self, user_id):
        self.query(AuthSession).filter(AuthSession.user_id == user_id).delete()

    def delete_verification_tokens(self, user_id):
        self.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user_id).delete()

    def delete_unused_reset_tokens(self, user_id):
        self.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None)
        ).delete()
