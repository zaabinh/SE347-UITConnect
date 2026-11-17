Run from `backend/` using the configured `DATABASE_URL`:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

This refactor does not introduce a schema migration or modify an existing database.
The versions directory starts empty; `alembic upgrade head` alone does not create
the application's tables. Existing setup and SQL upgrades remain available through
`python -m scripts.setup_local_db --wait 90` and `python -m scripts.upgrade_db`.
Review generated revisions before applying them, especially when establishing the
first migration for an existing SQL Server database.
