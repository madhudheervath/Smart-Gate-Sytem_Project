from __future__ import annotations

from sqlalchemy import inspect, text


ADDITIVE_COLUMNS = {
    "users": {
        "active": "BOOLEAN DEFAULT TRUE",
        "guardian_name": "VARCHAR(120)",
        "valid_until": "TIMESTAMP",
        "face_encoding": "TEXT",
        "face_registered": "BOOLEAN DEFAULT FALSE",
        "face_registered_at": "TIMESTAMP",
        "fcm_token": "TEXT",
        "phone": "VARCHAR(20)",
        "parent_name": "VARCHAR(120)",
        "parent_phone": "VARCHAR(20)",
        "parent_fcm_token": "TEXT",
        "notification_preferences": "TEXT DEFAULT '{}'",
        "last_notification_at": "TIMESTAMP",
    },
    "passes": {
        "pass_type": "VARCHAR(10) DEFAULT 'entry'",
        "approved_time": "TIMESTAMP",
        "used_by": "INTEGER",
        "request_latitude": "TEXT",
        "request_longitude": "TEXT",
        "location_verified": "BOOLEAN DEFAULT FALSE",
        "location_distance_km": "TEXT",
    },
    "scan_logs": {
        "pass_type": "VARCHAR(10) DEFAULT 'entry'",
        "emergency": "BOOLEAN DEFAULT FALSE",
        "details": "TEXT",
    },
}


def ensure_runtime_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements = []

    for table_name, columns in ADDITIVE_COLUMNS.items():
        if table_name not in table_names:
            continue

        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, definition in columns.items():
            if column_name not in existing_columns:
                statements.append(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                )

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(statement)

    print(f"✅ Runtime schema updated: added {len(statements)} missing column(s)")
