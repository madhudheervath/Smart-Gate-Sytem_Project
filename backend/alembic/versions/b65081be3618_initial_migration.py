"""Safe baseline migration for the current schema.

Revision ID: b65081be3618
Revises: 
Create Date: 2026-03-05 22:43:10.565191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b65081be3618'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    """Create missing tables and additive columns without deleting existing data."""
    bind = op.get_bind()

    from database import Base
    import models  # noqa: F401

    Base.metadata.create_all(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)

    additive_columns = {
        "users": {
            "active": lambda: sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
            "guardian_name": lambda: sa.Column("guardian_name", sa.String(length=120), nullable=True),
            "valid_until": lambda: sa.Column("valid_until", sa.DateTime(), nullable=True),
            "face_encoding": lambda: sa.Column("face_encoding", sa.Text(), nullable=True),
            "face_registered": lambda: sa.Column("face_registered", sa.Boolean(), nullable=True, server_default=sa.false()),
            "face_registered_at": lambda: sa.Column("face_registered_at", sa.DateTime(), nullable=True),
            "fcm_token": lambda: sa.Column("fcm_token", sa.Text(), nullable=True),
            "phone": lambda: sa.Column("phone", sa.String(length=20), nullable=True),
            "parent_name": lambda: sa.Column("parent_name", sa.String(length=120), nullable=True),
            "parent_phone": lambda: sa.Column("parent_phone", sa.String(length=20), nullable=True),
            "parent_fcm_token": lambda: sa.Column("parent_fcm_token", sa.Text(), nullable=True),
            "notification_preferences": lambda: sa.Column("notification_preferences", sa.Text(), nullable=True, server_default=sa.text("'{}'")),
            "last_notification_at": lambda: sa.Column("last_notification_at", sa.DateTime(), nullable=True),
        },
        "passes": {
            "pass_type": lambda: sa.Column("pass_type", sa.String(length=10), nullable=True, server_default=sa.text("'entry'")),
            "approved_time": lambda: sa.Column("approved_time", sa.DateTime(), nullable=True),
            "used_by": lambda: sa.Column("used_by", sa.Integer(), nullable=True),
            "request_latitude": lambda: sa.Column("request_latitude", sa.Text(), nullable=True),
            "request_longitude": lambda: sa.Column("request_longitude", sa.Text(), nullable=True),
            "location_verified": lambda: sa.Column("location_verified", sa.Boolean(), nullable=True, server_default=sa.false()),
            "location_distance_km": lambda: sa.Column("location_distance_km", sa.Text(), nullable=True),
        },
        "scan_logs": {
            "pass_type": lambda: sa.Column("pass_type", sa.String(length=10), nullable=True, server_default=sa.text("'entry'")),
            "emergency": lambda: sa.Column("emergency", sa.Boolean(), nullable=True, server_default=sa.false()),
            "details": lambda: sa.Column("details", sa.Text(), nullable=True),
        },
    }

    for table_name, columns in additive_columns.items():
        if table_name not in inspector.get_table_names():
            continue

        for column_name, factory in columns.items():
            if not _column_exists(inspector, table_name, column_name):
                op.add_column(table_name, factory())

        inspector = sa.inspect(bind)


def downgrade() -> None:
    """No-op downgrade.

    This repository has existing SQLite databases in active use, so the baseline
    migration intentionally avoids destructive downgrade behavior.
    """
