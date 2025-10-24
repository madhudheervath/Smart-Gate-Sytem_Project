"""
Database migration to add face authentication support
"""
import sqlite3
import shutil
from datetime import datetime

# Backup existing database
print("Creating backup of existing database...")
try:
    shutil.copy('gatepass.db', f'gatepass_backup_face_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    print("✅ Backup created")
except FileNotFoundError:
    print("⚠️  No existing database found - will create new one")

# Connect to database
conn = sqlite3.connect('gatepass.db')
cursor = conn.cursor()

print("\nMigrating database schema for face authentication...")
print("=" * 60)

try:
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'face_encoding' not in columns:
        print("Adding column: face_encoding (stores 128-D face vector as JSON)")
        cursor.execute("ALTER TABLE users ADD COLUMN face_encoding TEXT")
    
    if 'face_registered' not in columns:
        print("Adding column: face_registered (boolean flag)")
        cursor.execute("ALTER TABLE users ADD COLUMN face_registered BOOLEAN DEFAULT 0")
    
    if 'face_registered_at' not in columns:
        print("Adding column: face_registered_at (timestamp)")
        cursor.execute("ALTER TABLE users ADD COLUMN face_registered_at TIMESTAMP")
    
    conn.commit()
    print("=" * 60)
    print("✅ Database migration completed successfully!")
    
except sqlite3.Error as e:
    print(f"❌ Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n✅ Face authentication schema ready!")
print("Next steps:")
print("  1. Install face recognition: pip install face-recognition pillow")
print("  2. Test with: python -c 'import face_recognition; print(\"OK\")'")
