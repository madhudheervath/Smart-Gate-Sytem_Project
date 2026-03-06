#!/usr/bin/env python3

from migration_notice import print_deprecated_migration_notice


if __name__ == "__main__":
    print_deprecated_migration_notice(
        "add_emergency_column.py",
        "Legacy emergency flag migration for scan_logs",
    )
