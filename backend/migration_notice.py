from pathlib import Path


def print_deprecated_migration_notice(script_name: str, purpose: str) -> None:
    backend_dir = Path(__file__).resolve().parent
    alembic_ini = backend_dir / "alembic.ini"

    print("=" * 72)
    print(f"DEPRECATED SCRIPT: {script_name}")
    print("=" * 72)
    print(f"Purpose: {purpose}")
    print("")
    print("This repository now uses a single supported schema path:")
    print("1. `python bootstrap.py` to create tables and optionally seed demo data")
    print(f"2. `alembic -c {alembic_ini} upgrade head` for schema migrations")
    print("")
    print("This legacy raw-SQL migration script no longer changes the database.")
    print("Review the current Alembic baseline and SQLAlchemy models instead.")
    print("=" * 72)
