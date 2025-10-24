#!/usr/bin/env python3
"""
Add emergency column to scan_logs table for emergency exit feature
"""

from sqlalchemy import text
from database import engine, SessionLocal

def add_emergency_column():
    """Add emergency boolean column to scan_logs table"""
    
    db = SessionLocal()
    
    try:
        # Try to add the column (will fail if it exists)
        db.execute(text("""
            ALTER TABLE scan_logs 
            ADD COLUMN emergency BOOLEAN DEFAULT FALSE
        """))
        
        db.commit()
        print("✅ Emergency column added successfully to scan_logs table")
        
    except Exception as e:
        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
            print("✅ Emergency column already exists")
        else:
            print(f"❌ Error: {e}")
            db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Adding Emergency Column to Database")
    print("="*60 + "\n")
    
    add_emergency_column()
    
    print("\n" + "="*60)
    print("✅ Database migration complete!")
    print("="*60 + "\n")
