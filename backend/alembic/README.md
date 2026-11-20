# Versioned SQL Server schema

Run commands from `backend/`, using the target environment's settings. The API
launcher never runs migrations. A dedicated deployment process runs them before
application deployment. Use a migration database user with DDL privileges, separate
from the application's runtime user.

Current head is `20261119_02`, the additive outbox migration. Apply it before
deploying the Application Service / Unit of Work API and its separate worker;
see [the transaction runbook](../../docs/BACKEND_TRANSACTIONS.md).
`verify` and `adopt` below compare the **baseline** for initial adoption only;
they are not head-schema verification commands after applying later revisions.

## Verified baseline

Revision `20261119_01` was captured from the live SQL Server catalogs on 2026-11-19:
16 application tables, 46 indexes (including primary-key indexes), 31 foreign keys,
and no CHECK constraints, views, triggers or routines. The example SQL file has
constraints that do not exist in that database; it is not the baseline source.

- `baseline_schema.json`: catalog metadata only, no application rows or credentials.
- `baseline.sql`: frozen, forward-only creation DDL derived from that catalog.
- `versions/20261119_01_baseline.py`: executes those statements on an empty database.
- Checksums in `scripts/migration_policy.py` detect accidental artifact edits.

Do not regenerate this revision from current ORM classes. Future changes belong in
new revisions. Snapshot comparison includes column types, nullability, collation,
defaults, identity configuration, index keys/options, foreign keys and trust state.
Unrepresented SQL Server features require manual DDL review before baselining.

## Existing database adoption

```powershell
python -m scripts.migrate inventory --output .tmp/schema-inventory.json
python -m scripts.migrate verify
python -m scripts.migrate adopt
python -m scripts.migrate status
```

`adopt` verifies the actual catalog and stamps **the explicit baseline revision**.
It does not execute baseline CREATE statements or touch application rows. The
normal `alembic stamp 20261119_01` path also verifies equivalence in the migration
transaction and rolls back if it differs. Stamping arbitrary revisions or offline
stamping is refused. A database with drift must be investigated, not force-stamped.

The configured database was adopted and verified without backup, as explicitly
requested. See `BASELINE_VERIFICATION.md` for the validation performed.

## Empty database and deploy step

```powershell
# The database already exists and is empty:
python -m scripts.migrate upgrade

# Local convenience: create the database if absent, then run Alembic:
python -m scripts.setup_local_db --wait 90

# Confirm ORM metadata has no unintended differences:
python -m alembic check
```

Schema creation is entirely versioned. Use `python -m scripts.migrate upgrade`
to apply Alembic revisions. The legacy initialization and upgrade commands,
destructive `--reset`, ORM `create_all`, and raw SQL upgrade runner are removed.
Historical SQL files are references and must not be executed on a versioned DB.
An empty target must use the baseline's `SQL_Latin1_General_CP1_CI_AS` database
collation. The local setup helper uses that collation when creating a database;
it never changes the collation of an existing database.

Every online migration holds a database-scoped SQL Server `sp_getapplock` for its
transaction. A concurrent migrator fails fast. DDL and revision metadata share the
transaction; scripts must not open independent transactions or change NOCOUNT.
Baseline downgrade is deliberately disabled because it would destroy the schema.

## Expand, backfill, contract

1. **Expand** in one release: add nullable columns, new tables or non-unique indexes.
   Keep old columns and old behavior usable. Deploy compatible application code,
   using dual writes/fallback reads where the feature requires them.
2. **Backfill** as a separate bounded, idempotent job with checkpoints. Verify
   remaining rows and consistency; do not hold a schema migration transaction for
   a large data backfill.
3. Switch reads, verify behavior and retire all old web/background workers. Keep
   the expand schema through the application's rollback window.
4. **Contract** in a later release: remove old columns/paths or enforce restrictive
   constraints only after the previous conditions are verified.

```powershell
python -m scripts.migrate revision --phase expand --autogenerate -m "add nullable field"
# Review and apply the specific expand revision, not a later contract head:
python -m scripts.migrate upgrade <expand_revision>

# After compatible code rollout, backfill and retirement of old workers:
python -m scripts.migrate revision --phase contract -m "remove retired field"
python -m scripts.migrate upgrade <contract_revision> --allow-contract
```

New revision templates call `require_phase()` before operations. Contract revisions
and destructive downgrades require an explicit opt-in (`--allow-contract`, or
`alembic -x allow_contract=true ...`). This flag is an operator assertion, not proof
that backfill or worker retirement happened. Autogenerate rejects destructive,
restrictive or raw-SQL operations in the expand phase. Handwritten migrations still
need review; additive DDL is not a promise of lock-free/zero-downtime execution.

## CI and release workflow

```powershell
python -m pytest -q
python -m scripts.verify_migrations
```

The second command requires SQL Server and permission to create a **disposable**
`UITConnect_Alembic_Verify_*` database. It never resets the configured database.
It tests empty replay, idempotent upgrades, rejection of drift, data-preserving
adoption, concurrent migration locking, and expand/backfill/contract rollback/gates.
It deletes only its own newly created test database.

CI runs that same check against SQL Server 2022. The separate GitHub Actions
`Database migrations` workflow is manually dispatched for `staging` or `production`.
Configure the selected GitHub environment's `DATABASE_URL`, `JWT_SECRET_KEY`,
`FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` secrets. Allow network access from the
runner to the target SQL Server, or use a suitable private runner.

Run the workflow for the reviewed release commit and explicit upgrade revision,
then deploy that application release after it succeeds. This workflow does not
trigger Render deployments or change its auto-deploy configuration; coordinate
Render's deployment trigger so it cannot race ahead of the migration step.
