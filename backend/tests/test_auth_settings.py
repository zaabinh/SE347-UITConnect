from types import SimpleNamespace
from unittest.mock import Mock

from app.core.config import settings
from app.core.security import decode_token
from app.modules.auth.router import create_session_tokens, refresh_token
from app.modules.auth.schemas import RefreshTokenRequest


def test_session_and_refresh_use_validated_token_settings():
    user = SimpleNamespace(id="user-id", email="user@example.com", role="Student", status="active")
    request = SimpleNamespace(client=None, headers={})
    db = Mock()
    tokens = create_session_tokens(user, request, db)
    assert tokens.expires_in == settings.access_token_expire_minutes * 60
    assert decode_token(tokens.access_token)["sub"] == user.id
    assert decode_token(tokens.refresh_token)["type"] == "refresh"

    session = db.add.call_args.args[0]
    db.query.return_value.filter.return_value.first.side_effect = [session, user]
    refreshed = refresh_token(RefreshTokenRequest(refresh_token=tokens.refresh_token), db)
    assert refreshed.expires_in == tokens.expires_in
    assert decode_token(refreshed.access_token)["type"] == "access"
