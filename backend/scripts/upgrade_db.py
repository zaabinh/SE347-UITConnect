"""Compatibility command: apply Alembic revisions as a deployment step."""

from alembic import command

from scripts.migrate import alembic_config


def main() -> None:
    command.upgrade(alembic_config(), 'head')
    print('Versioned database migrations completed.')


if __name__ == "__main__":
    main()
