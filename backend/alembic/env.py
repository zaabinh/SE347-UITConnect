"""Alembic uses the same configuration and model registry as the API."""

from alembic import context

import app.modules  # noqa: F401 - register all domain models
from app.core.config import settings
from app.db.base import Base
from scripts.migration_policy import review_autogenerate, verify_version_step

target_metadata = Base.metadata


def include_object(obj, name, kind, reflected, compare_to):
    # SQL Server reflects the default dbo schema as None during autogenerate.
    return not (kind == 'table' and name == 'alembic_version' and obj.schema in {None, 'dbo'})


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        on_version_apply=verify_version_step,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from app.db.session import engine
    from sqlalchemy import text

    def migrate(connection):
        if connection.dialect.name != 'mssql':
            raise RuntimeError('Versioned schema migrations require SQL Server.')
        context.configure(
            connection=connection, target_metadata=target_metadata,
            compare_type=True, transactional_ddl=True,
            version_table_schema='dbo',
            on_version_apply=verify_version_step,
            process_revision_directives=review_autogenerate,
            include_object=include_object,
        )
        with context.begin_transaction():
            result = connection.execute(text("""
                SET NOCOUNT ON;
                DECLARE @result int;
                EXEC @result=sys.sp_getapplock @Resource=N'uitconnect:schema:migrations',
                    @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=0;
                SET NOCOUNT OFF;
                SELECT @result;
            """)).scalar_one()
            if result < 0:
                raise RuntimeError('Another schema migration is running; retry after it finishes.')
            context.run_migrations()

    supplied = context.config.attributes.get('connection')
    if supplied is not None:
        migrate(supplied)
    else:
        with engine.connect() as connection:
            migrate(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
