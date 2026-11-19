"""Durable side effects written in the same transaction as application changes."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, UnicodeText, and_, or_, select, update
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.repository import Repository
from app.db.uow import UnitOfWork


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class OutboxEvent(Base):
    __tablename__ = 'outbox_events'
    __table_args__ = (Index('ix_outbox_events_dispatch', 'status', 'available_at'),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', server_default='pending')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    lock_token: Mapped[str | None] = mapped_column(String(36))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(100))


def enqueue_email(db, recipient: str, subject: str, body: str) -> OutboxEvent:
    if not db.info.get('unit_of_work'):
        raise RuntimeError('Outbox events must be enqueued inside an application unit of work.')
    return Repository(db).add(OutboxEvent(
        event_type='email.send',
        payload=json.dumps({'recipient': recipient, 'subject': subject, 'body': body}, ensure_ascii=False),
    ))


class OutboxRepository(Repository):
    def eligible(self, now):
        return or_(
            and_(OutboxEvent.status == 'pending', OutboxEvent.available_at <= now),
            and_(OutboxEvent.status == 'processing', OutboxEvent.locked_at < now - timedelta(minutes=5)),
        )

    def claim(self, now):
        ids = self.execute(select(OutboxEvent.id).where(self.eligible(now))
                           .order_by(OutboxEvent.available_at, OutboxEvent.id).limit(20)).scalars().all()
        for event_id in ids:
            token = str(uuid4())
            claimed = self.execute(update(OutboxEvent).where(
                OutboxEvent.id == event_id, self.eligible(now),
            ).values(status='processing', locked_at=now, lock_token=token,
                     attempts=OutboxEvent.attempts + 1).execution_options(synchronize_session=False))
            if claimed.rowcount == 1:
                event = self.session.get(OutboxEvent, event_id)
                return event.id, token, event.event_type, event.payload, event.attempts
        return None

    def finish(self, event_id, token, attempts, error=None):
        now = utcnow()
        values = {'lock_token': None, 'locked_at': None}
        if error is None:
            # Delivery payload contains private reset links; discard it after acknowledgement.
            values.update(status='processed', processed_at=now, last_error=None, payload='{}')
        else:
            values.update(status='failed' if attempts >= 8 else 'pending',
                          available_at=now + timedelta(seconds=min(30 * 2 ** min(attempts, 8), 3600)),
                          last_error=type(error).__name__[:100])
        self.execute(update(OutboxEvent).where(
            OutboxEvent.id == event_id, OutboxEvent.lock_token == token,
            OutboxEvent.status == 'processing',
        ).values(**values))


def dispatch_one(session_factory, send_email=None) -> bool:
    if send_email is None:
        from app.modules.auth.email_service import send_email_message
        send_email = send_email_message
    with session_factory() as db:
        with UnitOfWork(db):
            claimed = OutboxRepository(db).claim(utcnow())
    if claimed is None:
        return False
    event_id, token, event_type, payload, attempts = claimed
    error = None
    try:
        if event_type != 'email.send':
            raise ValueError('Unsupported outbox event type.')
        send_email(**json.loads(payload), idempotency_key=event_id)
    except Exception as exc:
        error = exc
    with session_factory() as db:
        with UnitOfWork(db):
            OutboxRepository(db).finish(event_id, token, attempts, error)
    return True
