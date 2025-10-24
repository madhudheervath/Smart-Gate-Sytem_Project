import sqlite3

# Add pass_type columns to existing database
conn = sqlite3.connect('gatepass.db')
cursor = conn.cursor()

try:
    # Add pass_type to passes table
    cursor.execute("ALTER TABLE passes ADD COLUMN pass_type VARCHAR(10) DEFAULT 'entry'")
    print("Added pass_type column to passes table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("pass_type column already exists in passes table")
    else:
        print(f"Error adding pass_type to passes: {e}")

try:
    # Add pass_type to scan_logs table
    cursor.execute("ALTER TABLE scan_logs ADD COLUMN pass_type VARCHAR(10) DEFAULT 'entry'")
    print("Added pass_type column to scan_logs table")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("pass_type column already exists in scan_logs table")
    else:
        print(f"Error adding pass_type to scan_logs: {e}")

conn.commit()
conn.close()
print("Migration completed successfully!")

