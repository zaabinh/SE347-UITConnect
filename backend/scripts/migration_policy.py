"""Baseline verification and explicit expand/contract migration boundaries."""

import json
from hashlib import sha256
from pathlib import Path

from alembic import context
from alembic.operations import ops

from scripts.db_schema import differences, inventory, split_batches

BASELINE_REVISION = '20261119_01'
MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / 'alembic'
# Set once when the verified live catalog is captured; never regenerate on startup.
SCHEMA_SHA256 = '6152179ebac39af13b6f01306e11a17172e7686ed6178afbb6d5d5a4388ad910'
DDL_SHA256 = '4868acea839d6dcbfc849b1ece812e93444c2593474ddc71aa71a44f0af8080b'


def baseline_snapshot() -> dict:
    content = (MIGRATIONS_DIR / 'baseline_schema.json').read_bytes().replace(b'\r\n', b'\n')
    if sha256(content).hexdigest() != SCHEMA_SHA256:
        raise RuntimeError('Frozen baseline schema checksum changed; restore the reviewed artifact.')
    return json.loads(content)


def baseline_statements() -> list[str]:
    content = (MIGRATIONS_DIR / 'baseline.sql').read_bytes().replace(b'\r\n', b'\n')
    if sha256(content).hexdigest() != DDL_SHA256:
        raise RuntimeError('Frozen baseline DDL checksum changed; restore the reviewed artifact.')
    return split_batches(content.decode('utf-8'))


def verify_baseline(connection) -> None:
    drift = differences(baseline_snapshot(), inventory(connection))
    if drift:
        raise RuntimeError('Schema differs from verified baseline; refusing adoption:\n' + '\n'.join(drift[:30]))


def verify_version_step(ctx, step, heads, run_args) -> None:
    if ctx.as_sql:
        if step.is_stamp:
            raise RuntimeError('Offline stamping cannot verify an existing SQL Server schema.')
        return
    if step.is_stamp:
        if step.destination_revision_ids != (BASELINE_REVISION,) or step.source_revision_ids:
            raise RuntimeError('Only adoption of an unversioned database at the baseline may be stamped.')
        verify_baseline(ctx.bind)
    elif step.is_upgrade and step.up_revision_id == BASELINE_REVISION:
        verify_baseline(ctx.bind)


def require_phase(phase: str) -> None:
    if phase not in {'expand', 'contract'}:
        raise RuntimeError('Migration phase must be expand or contract.')
    allowed = context.config.attributes.get('allow_contract', False)
    allowed = allowed or context.get_x_argument(as_dictionary=True).get('allow_contract') == 'true'
    if phase == 'contract' and not allowed:
        raise RuntimeError('Contract migrations require an explicit --allow-contract or -x allow_contract=true after backfill and old-worker retirement.')


def validate_expand(operation) -> None:
    if isinstance(operation, (ops.UpgradeOps, ops.ModifyTableOps)):
        for child in operation.ops:
            validate_expand(child)
    elif isinstance(operation, ops.CreateTableOp):
        return
    elif isinstance(operation, ops.AddColumnOp) and operation.column.nullable is True:
        return
    elif isinstance(operation, ops.CreateIndexOp) and not operation.unique:
        return
    else:
        raise RuntimeError(f'{type(operation).__name__} requires manual review; expand autogenerate only permits new tables, nullable columns and non-unique indexes.')


def review_autogenerate(migration_context, revision, directives) -> None:
    phase = context.config.attributes.get('migration_phase', 'expand')
    if phase == 'expand':
        for directive in directives:
            for operations in directive.upgrade_ops_list:
                validate_expand(operations)
