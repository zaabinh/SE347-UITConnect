import json
from urllib.request import Request, urlopen

from app.core.config import settings


FRONTEND_URL = str(settings.frontend_url).rstrip("/")


def build_verification_link(token: str) -> str:
    return f"{FRONTEND_URL}/verify-email?token={token}"


def build_password_reset_link(token: str) -> str:
    return f"{FRONTEND_URL}/reset-password?token={token}"


def send_email_message(recipient: str, subject: str, body: str, *, idempotency_key: str) -> None:
    if not settings.resend_api_key:
        raise RuntimeError('Configure RESEND_API_KEY before dispatching email events.')
    request = Request(
        'https://api.resend.com/emails',
        data=json.dumps({'from': settings.mail_from, 'to': [recipient], 'subject': subject, 'text': body}).encode(),
        headers={'Authorization': f'Bearer {settings.resend_api_key}',
                 'Content-Type': 'application/json', 'Idempotency-Key': idempotency_key,
                 'User-Agent': 'UITConnect/1.0'},
        method='POST',
    )
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
        if not result.get('id'):
            raise RuntimeError('Email provider did not acknowledge the message.')
