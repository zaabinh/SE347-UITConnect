from io import StringIO
from types import SimpleNamespace
from shutil import copyfile

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.operations import ops

from app.core import config as configuration
from scripts import migration_policy as policy
from scripts.db_schema import differences, inventory, quote, split_batches
from scripts.migrate import alembic_config


def test_frozen_live_baseline_and_offline_replay(monkeypatch):
    snapshot = policy.baseline_snapshot()
    assert len(snapshot['tables']) == 16
    assert sum(len(table['foreign_keys']) for table in snapshot['tables']) == 31
    monkeypatch.setattr(configuration, 'settings', configuration.settings.model_copy(update={
        'database_url': 'mssql+pyodbc://offline/unused?driver=ODBC+Driver+18+for+SQL+Server',
    }))
    config = alembic_config()
    config.output_buffer = StringIO()
    command.upgrade(config, policy.BASELINE_REVISION, sql=True)
    ddl = config.output_buffer.getvalue()
    assert 'CREATE TABLE [dbo].[users]' in ddl
    assert 'CREATE TABLE [dbo].[notifications]' in ddl
    assert 'CREATE INDEX' in ddl or 'CREATE NONCLUSTERED INDEX' in ddl
    assert 'DROP TABLE' not in ddl


def test_baseline_artifact_tampering_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(policy, 'MIGRATIONS_DIR', tmp_path)
    (tmp_path / 'baseline.sql').write_text('DROP TABLE dbo.users')
    (tmp_path / 'baseline_schema.json').write_text('{}')
    with pytest.raises(RuntimeError, match='checksum changed'):
        policy.baseline_statements()
    with pytest.raises(RuntimeError, match='checksum changed'):
        policy.baseline_snapshot()


def test_schema_drift_rejects_adoption(monkeypatch):
    expected = policy.baseline_snapshot()
    monkeypatch.setattr(policy, 'inventory', lambda connection: {**expected, 'tables': []})
    with pytest.raises(RuntimeError, match='Schema differs'):
        policy.verify_baseline(object())


def test_catalog_verification_refuses_sqlite():
    with sa.create_engine('sqlite://').connect() as connection:
        with pytest.raises(RuntimeError, match='requires SQL Server'):
            inventory(connection)


@pytest.mark.parametrize('operation', [
    ops.DropTableOp('users'),
    ops.DropColumnOp('users', 'email'),
    ops.AlterColumnOp('users', 'email', modify_nullable=False),
    ops.AddColumnOp('users', sa.Column('new_value', sa.Integer(), nullable=False)),
    ops.CreateIndexOp('unique_value', 'users', ['email'], unique=True),
    ops.ExecuteSQLOp('DELETE FROM users'),
])
def test_expand_autogenerate_rejects_destructive_or_restrictive_changes(operation):
    with pytest.raises(RuntimeError, match='requires manual review'):
        policy.validate_expand(ops.UpgradeOps([operation]))


def test_expand_autogenerate_accepts_additive_changes():
    policy.validate_expand(ops.UpgradeOps([
        ops.CreateTableOp('new_table', [sa.Column('id', sa.Integer(), primary_key=True)]),
        ops.ModifyTableOps('users', [ops.AddColumnOp('users', sa.Column('new_value', sa.Integer(), nullable=True))]),
        ops.CreateIndexOp('lookup_email', 'users', ['email'], unique=False),
    ]))


def test_contract_requires_explicit_opt_in(monkeypatch):
    config = SimpleNamespace(attributes={})
    monkeypatch.setattr(policy.context, 'config', config, raising=False)
    monkeypatch.setattr(policy.context, 'get_x_argument', lambda **kwargs: {})
    policy.require_phase('expand')
    with pytest.raises(RuntimeError, match='Contract migrations require'):
        policy.require_phase('contract')
    config.attributes['allow_contract'] = True
    policy.require_phase('contract')


def test_metadata_comparison_and_sql_batch_boundaries():
    assert differences({'index': {'unique': False}}, {'index': {'unique': True}})
    assert differences({'columns': ['a']}, {'columns': ['a']}) == []
    assert split_batches('SELECT 1\nGO\n\nSELECT 2\ngo\n') == ['SELECT 1', 'SELECT 2']
    assert quote('name]part') == '[name]]part]'


def test_revision_template_preserves_phase_and_enforces_guard(monkeypatch, tmp_path):
    (tmp_path / 'versions').mkdir()
    copyfile(policy.MIGRATIONS_DIR / 'script.py.mako', tmp_path / 'script.py.mako')
    config = alembic_config()
    config.set_main_option('script_location', str(tmp_path))
    config.attributes['migration_phase'] = 'contract'
    revision = command.revision(config, message='contract template probe')
    assert revision.module.migration_phase == 'contract'
    calls = []
    monkeypatch.setattr(revision.module, 'require_phase', lambda phase: calls.append(phase))
    revision.module.upgrade()
    revision.module.downgrade()
    assert calls == ['contract', 'contract']
