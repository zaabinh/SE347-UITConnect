# Baseline verification — 2026-11-19

- Source: connected SQL Server Express, read directly through `sys.*` catalogs.
- Schema: 16 application tables, 46 indexes, 31 foreign keys, 0 CHECK constraints.
- Additional views, triggers, stored procedures, functions, sequences and synonyms: 0.
- Database collation: `SQL_Latin1_General_CP1_CI_AS`.
- Backup/restore exercise: skipped at the user's explicit request.

Validation performed on newly created disposable SQL Server databases:

1. Replayed baseline `20261119_01` on an empty database.
2. Compared the resulting catalog against the captured source: exact match.
3. Re-ran upgrade: no schema changes.
4. Added deliberate drift: stamping was rejected and version metadata rolled back.
5. Adopted an equivalent unversioned schema: an existing probe row was preserved.
6. Held the migration lock: a concurrent migrator was rejected.
7. Applied an expand revision, backfilled its nullable field, and tested contract:
   rejected without opt-in with revision/data preserved; succeeded with explicit opt-in.
8. Removed the disposable databases and temporary probe revisions.

Source adoption:

- Reverified the source catalog before and during `stamp`.
- Applied **only** Alembic metadata at revision `20261119_01`.
- Verified row counts of all 16 application tables were unchanged before/after.
- Rechecked the source catalog against the frozen baseline: exact match.
- Aligned the ORM index name `IX_comments_status` with its existing SQL Server name;
  no index was recreated. `alembic check` reports no new upgrade operations.

No application table was created, dropped, altered or backfilled in the source DB.
Only `dbo.alembic_version` was added. Future feature migrations have not been applied.
