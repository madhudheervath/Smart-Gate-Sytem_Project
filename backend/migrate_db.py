"""
Database migration to add student fields to users table
"""
import sqlite3
import shutil
from datetime import datetime

# Backup existing database
print("Creating backup of existing database...")
try:
    shutil.copy('gatepass.db', f'gatepass_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    print("✅ Backup created")
except FileNotFoundError:
    print("⚠️  No existing database found - will create new one")

# Connect to database
conn = sqlite3.connect('gatepass.db')
cursor = conn.cursor()

print("\nMigrating database schema...")
print("=" * 60)

try:
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'student_id' not in columns:
        print("Adding column: student_id")
        cursor.execute("ALTER TABLE users ADD COLUMN student_id TEXT")
    
    if 'student_class' not in columns:
        print("Adding column: student_class")
        cursor.execute("ALTER TABLE users ADD COLUMN student_class TEXT")
    
    if 'guardian_name' not in columns:
        print("Adding column: guardian_name")
        cursor.execute("ALTER TABLE users ADD COLUMN guardian_name TEXT")
    
    if 'valid_until' not in columns:
        print("Adding column: valid_until")
        cursor.execute("ALTER TABLE users ADD COLUMN valid_until TIMESTAMP")
    
    conn.commit()
    print("=" * 60)
    print("✅ Database migration completed successfully!")
    
except sqlite3.Error as e:
    print(f"❌ Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n✅ You can now run: python add_students.py")

