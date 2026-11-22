"""Exercise migrations on a disposable SQL Server database, never on application tables."""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.session import engine as configured_engine
from app.db.outbox import OutboxEvent, dispatch_one, enqueue_email
from app.db.uow import UnitOfWork
from scripts.db_schema import collation_name, inventory, quote
from scripts.migrate import alembic_config
from scripts.migration_policy import BASELINE_REVISION, MIGRATIONS_DIR, baseline_snapshot, verify_baseline


def apply(engine, config, operation, *args) -> None:
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        operation(config, *args)
    config.attributes.pop('connection', None)


def expect_rejection(call, message: str) -> None:
    try:
        call()
    except RuntimeError as exc:
        if message not in str(exc):
            raise
    else:
        raise AssertionError(f'Expected migration rejection: {message}')


def main() -> None:
    if configured_engine.dialect.name != 'mssql':
        raise RuntimeError('Integration verification requires SQL Server and CREATE ANY DATABASE permission.')
    name = 'UITConnect_Alembic_Verify_' + uuid4().hex[:12]
    master = create_engine(configured_engine.url.set(database='master'), isolation_level='AUTOCOMMIT', hide_parameters=True)
    test_engine = None
    created = False
    try:
        expected = baseline_snapshot()
        with master.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE {quote(name)} COLLATE {collation_name(expected["collation"])}')
            created = True
        test_engine = create_engine(configured_engine.url.set(database=name), hide_parameters=True)
        config = alembic_config()
        current_head = ScriptDirectory.from_config(config).get_current_head()
        apply(test_engine, config, command.upgrade, BASELINE_REVISION)
        with test_engine.connect() as connection:
            verify_baseline(connection)
            assert connection.execute(text('SELECT version_num FROM dbo.alembic_version')).scalar_one() == BASELINE_REVISION
        apply(test_engine, config, command.upgrade, BASELINE_REVISION)
        print('PASS: empty SQL Server replay matches the captured catalog; repeat upgrade is a no-op.')

        # Preserve a real row while simulating adoption of a legacy unversioned schema.
        with test_engine.begin() as connection:
            connection.execute(text("INSERT INTO dbo.users(username,email,password_hash,full_name) VALUES ('migration_probe','probe@example.test','not-a-login-hash',N'Migration probe')"))
            connection.execute(text('DROP TABLE dbo.alembic_version'))
            connection.execute(text('ALTER TABLE dbo.users ADD migration_probe int NULL'))
        expect_rejection(lambda: apply(test_engine, config, command.stamp, BASELINE_REVISION), 'Schema differs')
        with test_engine.connect() as connection:
            assert not inspect(connection).has_table('alembic_version', schema='dbo')
        with test_engine.begin() as connection:
            connection.execute(text('ALTER TABLE dbo.users DROP COLUMN migration_probe'))
        expect_rejection(lambda: apply(test_engine, config, command.upgrade, 'head'), 'Database is not empty')
        apply(test_engine, config, command.stamp, BASELINE_REVISION)
        with test_engine.connect() as connection:
            verify_baseline(connection)
            assert connection.execute(text("SELECT COUNT(*) FROM dbo.users WHERE username='migration_probe'")).scalar_one() == 1
        print('PASS: drift refuses stamp and rolls back metadata; equivalent legacy adoption preserves data.')

        apply(test_engine, config, command.upgrade, 'head')
        with test_engine.connect() as connection:
            assert inspect(connection).has_table('outbox_events')
            assert connection.execute(text("SELECT COUNT(*) FROM dbo.users WHERE username='migration_probe'")).scalar_one() == 1
        print('PASS: outbox expand revision preserves existing application rows.')
        apply(test_engine, config, command.check)
        sessions = sessionmaker(test_engine)
        with sessions() as db:
            with UnitOfWork(db):
                event = enqueue_email(db, 'probe@example.test', 'Outbox probe', 'Unicode: tiếng Việt')
                db.flush()
                event_id = event.id
        sent = []
        assert dispatch_one(sessions, lambda **kwargs: sent.append(kwargs))
        assert not dispatch_one(sessions, lambda **kwargs: sent.append(kwargs))
        with sessions() as db:
            assert db.get(OutboxEvent, event_id).status == 'processed'
        assert sent[0]['idempotency_key'] == event_id and sent[0]['body'] == 'Unicode: tiếng Việt'
        print('PASS: SQL Server outbox claim/dispatch/ack and ORM schema comparison; no external email sent.')

        # A second migrator must fail fast while the first owns the database-scoped lock.
        with test_engine.begin() as connection:
            connection.execute(text("EXEC sys.sp_getapplock @Resource=N'uitconnect:schema:migrations', @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=0"))
            expect_rejection(lambda: apply(test_engine, config, command.upgrade, 'head'), 'Another schema migration')
        print('PASS: concurrent migration is rejected by the SQL Server application lock.')

        work = MIGRATIONS_DIR.parent / '.tmp'
        work.mkdir(exist_ok=True)
        with TemporaryDirectory(prefix='migration-policy-', dir=work) as temporary:
            assert Path(temporary).resolve().is_relative_to(work.resolve())
            migration_dir = Path(temporary) / 'alembic'
            shutil.copytree(MIGRATIONS_DIR, migration_dir)
            revisions = migration_dir / 'versions'
            (revisions / 'verification_expand.py').write_text('''from alembic import op
import sqlalchemy as sa
from scripts.migration_policy import require_phase
revision = 'verification_expand'
down_revision = '__CURRENT_HEAD__'
branch_labels = depends_on = None
migration_phase = 'expand'
def upgrade():
    require_phase(migration_phase)
    op.add_column('users', sa.Column('migration_probe', sa.Integer(), nullable=True), schema='dbo')
def downgrade():
    require_phase('contract')
    op.drop_column('users', 'migration_probe', schema='dbo')
'''.replace('__CURRENT_HEAD__', current_head), encoding='utf-8')
            (revisions / 'verification_contract.py').write_text('''from alembic import op
from scripts.migration_policy import require_phase
revision = 'verification_contract'
down_revision = 'verification_expand'
branch_labels = depends_on = None
migration_phase = 'contract'
def upgrade():
    require_phase(migration_phase)
    op.drop_column('users', 'migration_probe', schema='dbo')
def downgrade():
    raise RuntimeError('Restore application compatibility with a forward migration.')
''', encoding='utf-8')
            config = alembic_config()
            config.set_main_option('script_location', str(migration_dir))
            apply(test_engine, config, command.upgrade, 'verification_expand')
            with test_engine.begin() as connection:
                connection.execute(text('UPDATE dbo.users SET migration_probe=1 WHERE migration_probe IS NULL'))
            expect_rejection(lambda: apply(test_engine, config, command.upgrade, 'head'), 'Contract migrations require')
            with test_engine.connect() as connection:
                assert connection.execute(text('SELECT version_num FROM dbo.alembic_version')).scalar_one() == 'verification_expand'
                assert connection.execute(text('SELECT migration_probe FROM dbo.users')).scalar_one() == 1
            config.attributes['allow_contract'] = True
            apply(test_engine, config, command.upgrade, 'head')
            with test_engine.connect() as connection:
                assert 'migration_probe' not in {column['name'] for column in inspect(connection).get_columns('users', schema='dbo')}
                assert connection.execute(text('SELECT COUNT(*) FROM dbo.users')).scalar_one() == 1
        print('PASS: expand/backfill/contract lifecycle, explicit contract approval and rollback on rejection.')
    finally:
        if test_engine is not None:
            test_engine.dispose()
        if created:
            assert name.startswith('UITConnect_Alembic_Verify_') and name != configured_engine.url.database
            with master.connect() as connection:
                connection.exec_driver_sql(f'ALTER DATABASE {quote(name)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE')
                connection.exec_driver_sql(f'DROP DATABASE {quote(name)}')
            print('Removed only the disposable migration verification database.')
        master.dispose()
        configured_engine.dispose()


if __name__ == '__main__':
    main()
