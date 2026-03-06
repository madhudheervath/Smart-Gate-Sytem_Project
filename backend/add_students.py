from migration_notice import print_deprecated_migration_notice


if __name__ == "__main__":
    print_deprecated_migration_notice(
        "add_students.py",
        "Legacy student seed helper superseded by bootstrap.py and add_students_with_parents.py",
    )

