"""
Database migration to add GPS geofencing support
"""
import sqlite3
import shutil
from datetime import datetime

# Backup existing database
print("Creating backup of existing database...")
try:
    shutil.copy('gatepass.db', f'gatepass_backup_gps_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    print("✅ Backup created")
except FileNotFoundError:
    print("⚠️  No existing database found - will create new one")

# Connect to database
conn = sqlite3.connect('gatepass.db')
cursor = conn.cursor()

print("\nMigrating database schema for GPS geofencing...")
print("=" * 60)

try:
    # Check if columns already exist in passes table
    cursor.execute("PRAGMA table_info(passes)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'request_latitude' not in columns:
        print("Adding column: request_latitude")
        cursor.execute("ALTER TABLE passes ADD COLUMN request_latitude TEXT")
    
    if 'request_longitude' not in columns:
        print("Adding column: request_longitude")
        cursor.execute("ALTER TABLE passes ADD COLUMN request_longitude TEXT")
    
    if 'location_verified' not in columns:
        print("Adding column: location_verified")
        cursor.execute("ALTER TABLE passes ADD COLUMN location_verified BOOLEAN DEFAULT 0")
    
    if 'location_distance_km' not in columns:
        print("Adding column: location_distance_km")
        cursor.execute("ALTER TABLE passes ADD COLUMN location_distance_km TEXT")
    
    conn.commit()
    print("=" * 60)
    print("✅ Database migration completed successfully!")
    
except sqlite3.Error as e:
    print(f"❌ Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n✅ GPS geofencing schema ready!")
print("Next steps:")
print("  1. Install geofencing libraries: pip install shapely geopy")
print("  2. Configure campus boundary in backend/geofence.py")
print("  3. Test location validation")
