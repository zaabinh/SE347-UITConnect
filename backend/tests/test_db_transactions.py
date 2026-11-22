from datetime import timedelta
import json

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db.outbox import OutboxEvent, OutboxRepository, dispatch_one, enqueue_email, utcnow
from app.db.uow import UnitOfWork


@pytest.fixture
def sessions():
    engine = create_engine('sqlite://')
    OutboxEvent.__table__.create(engine)
    factory = sessionmaker(engine)
    yield factory
    engine.dispose()


def enqueue(sessions):
    with sessions() as db:
        with UnitOfWork(db):
            message = enqueue_email(db, 'student@example.test', 'Reset', 'private-reset-link')
            db.flush()
            event_id = message.id
    return event_id


def test_outbox_requires_uow_and_rolls_back_with_use_case(sessions):
    with sessions() as db:
        with pytest.raises(RuntimeError, match='unit of work'):
            enqueue_email(db, 'a@example.test', 'subject', 'body')
        with pytest.raises(ValueError):
            with UnitOfWork(db):
                enqueue_email(db, 'a@example.test', 'subject', 'body')
                db.flush()
                raise ValueError('failed after flush')
        assert db.scalars(select(OutboxEvent)).all() == []


def test_commit_failure_rolls_back_and_clears_owner(sessions):
    with sessions() as db:
        def fail_commit(session):
            raise RuntimeError('commit failed')
        event.listen(db, 'before_commit', fail_commit)
        with pytest.raises(RuntimeError, match='commit failed'):
            with UnitOfWork(db):
                enqueue_email(db, 'a@example.test', 'subject', 'body')
                db.flush()
        event.remove(db, 'before_commit', fail_commit)
        assert 'unit_of_work' not in db.info
        assert db.scalars(select(OutboxEvent)).all() == []


def test_auth_autobegin_supported_and_nested_uow_rejected(sessions):
    with sessions() as db:
        db.execute(select(OutboxEvent))
        assert db.in_transaction()
        with UnitOfWork(db):
            with pytest.raises(RuntimeError, match='Nested'):
                with UnitOfWork(db):
                    pytest.fail('nested transaction entered')
            enqueue_email(db, 'a@example.test', 'subject', 'body')
        assert len(db.scalars(select(OutboxEvent)).all()) == 1


def test_dispatch_observes_committed_event_and_acknowledges_once(sessions):
    event_id = enqueue(sessions)
    sent = []
    def send(**payload):
        with sessions() as db:
            assert db.get(OutboxEvent, event_id).status == 'processing'
        sent.append(payload)
    assert dispatch_one(sessions, send)
    assert not dispatch_one(sessions, send)
    assert sent[0]['idempotency_key'] == event_id
    assert sent[0]['body'] == 'private-reset-link'
    with sessions() as db:
        message = db.get(OutboxEvent, event_id)
        assert message.status == 'processed'
        assert message.processed_at is not None
        assert message.payload == '{}'


def test_failed_delivery_retries_same_event_without_leaking_error(sessions):
    event_id = enqueue(sessions)
    def fail(**kwargs):
        raise ValueError('private-reset-link and credentials')
    assert dispatch_one(sessions, fail)
    with sessions() as db:
        message = db.get(OutboxEvent, event_id)
        assert message.status == 'pending'
        assert message.attempts == 1
        assert message.last_error == 'ValueError'
        assert message.available_at > utcnow()
        with UnitOfWork(db):
            message.available_at = utcnow() - timedelta(seconds=1)
    sent = []
    assert dispatch_one(sessions, lambda **kwargs: sent.append(kwargs))
    assert sent[0]['idempotency_key'] == event_id


def test_worker_crash_recovery_reclaims_expired_lease_and_rejects_stale_ack(sessions):
    event_id = enqueue(sessions)
    with sessions() as db:
        with UnitOfWork(db):
            claimed = OutboxRepository(db).claim(utcnow())
    assert not dispatch_one(sessions, lambda **kwargs: pytest.fail('active lease delivered twice'))
    with sessions() as db:
        with UnitOfWork(db):
            db.get(OutboxEvent, event_id).locked_at = utcnow() - timedelta(minutes=6)
    with sessions() as db:
        with UnitOfWork(db):
            second = OutboxRepository(db).claim(utcnow())
    with sessions() as db:
        with UnitOfWork(db):
            OutboxRepository(db).finish(event_id, claimed[1], claimed[4])
        assert db.get(OutboxEvent, event_id).lock_token == second[1]


def test_repeated_failure_is_retained_for_operator_review(sessions):
    event_id = enqueue(sessions)
    with sessions() as db:
        with UnitOfWork(db):
            db.get(OutboxEvent, event_id).attempts = 7
    def fail(**kwargs):
        raise RuntimeError('provider down')
    assert dispatch_one(sessions, fail)
    with sessions() as db:
        assert db.get(OutboxEvent, event_id).status == 'failed'
    assert not dispatch_one(sessions, fail)


def test_email_adapter_uses_provider_idempotency_without_network(monkeypatch):
    from app.modules.auth import email_service
    monkeypatch.setattr(email_service, 'settings', email_service.settings.model_copy(update={'resend_api_key': 'test-key'}))
    from io import BytesIO
    captured = []
    def fake_open(request, timeout):
        captured.append((request, timeout))
        return BytesIO(b'{"id":"provider-id"}')
    monkeypatch.setattr(email_service, 'urlopen', fake_open)
    email_service.send_email_message('a@example.test', 'subject', 'body', idempotency_key='stable-event-id')
    request, timeout = captured[0]
    assert request.get_header('Idempotency-key') == 'stable-event-id'
    assert json.loads(request.data)['text'] == 'body'
    assert timeout == 20
