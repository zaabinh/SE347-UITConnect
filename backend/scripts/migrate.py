"""Separate schema deployment: inspect, verify, adopt, upgrade, or author a revision."""

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from scripts.db_schema import canonical, inventory
from scripts.migration_policy import BASELINE_REVISION, MIGRATIONS_DIR, verify_baseline


def alembic_config() -> Config:
    return Config(str(MIGRATIONS_DIR.parent / 'alembic.ini'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    inspect_parser = commands.add_parser('inventory', help='Read the actual SQL Server catalog, without table data.')
    inspect_parser.add_argument('--output', type=Path, required=True)
    commands.add_parser('verify', help='Compare the database against the frozen baseline.')
    commands.add_parser('adopt', help='Verify and stamp an existing, equivalent unversioned schema.')
    commands.add_parser('status', help='Show the applied Alembic revision.')
    upgrade = commands.add_parser('upgrade', help='Apply versioned migrations as a separate deployment step.')
    upgrade.add_argument('revision', nargs='?', default='head')
    upgrade.add_argument('--allow-contract', action='store_true')
    revision = commands.add_parser('revision', help='Author an expand or contract migration for review.')
    revision.add_argument('-m', '--message', required=True)
    revision.add_argument('--phase', choices=['expand', 'contract'], default='expand')
    revision.add_argument('--autogenerate', action='store_true')
    args = parser.parse_args()
    config = alembic_config()
    if args.operation == 'revision':
        config.attributes['migration_phase'] = args.phase
        command.revision(config, message=args.message, autogenerate=args.autogenerate)
        return
    from app.db.session import engine
    try:
        if args.operation == 'inventory':
            with engine.connect() as connection:
                content = canonical(inventory(connection))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding='utf-8', newline='\n')
            print(f'Schema inventory saved to {args.output}; no application data exported.')
        elif args.operation == 'verify':
            with engine.connect() as connection:
                verify_baseline(connection)
            print('Database matches the verified baseline.')
        elif args.operation == 'adopt':
            with engine.begin() as connection:
                verify_baseline(connection)
                config.attributes['connection'] = connection
                command.stamp(config, BASELINE_REVISION)
            print(f'Existing schema verified and stamped at {BASELINE_REVISION}; application tables unchanged.')
        elif args.operation == 'status':
            command.current(config, verbose=True)
        elif args.operation == 'upgrade':
            config.attributes['allow_contract'] = args.allow_contract
            command.upgrade(config, args.revision)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
