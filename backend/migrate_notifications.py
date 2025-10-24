"""
Database migration: Add notification fields
- FCM tokens for push notifications
- Parent/guardian contact information
- Notification preferences
"""

import sqlite3

DB_PATH = "gatepass.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 Adding notification fields to users table...")
    
    try:
        # Add FCM token for push notifications
        cursor.execute("""
            ALTER TABLE users ADD COLUMN fcm_token TEXT
        """)
        print("✅ Added fcm_token column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  fcm_token column already exists")
        else:
            raise
    
    try:
        # Add student phone number
        cursor.execute("""
            ALTER TABLE users ADD COLUMN phone TEXT
        """)
        print("✅ Added phone column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  phone column already exists")
        else:
            raise
    
    try:
        # Add parent/guardian name
        cursor.execute("""
            ALTER TABLE users ADD COLUMN parent_name TEXT
        """)
        print("✅ Added parent_name column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  parent_name column already exists")
        else:
            raise
    
    try:
        # Add parent/guardian phone
        cursor.execute("""
            ALTER TABLE users ADD COLUMN parent_phone TEXT
        """)
        print("✅ Added parent_phone column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  parent_phone column already exists")
        else:
            raise
    
    try:
        # Add parent FCM token (if they have the app)
        cursor.execute("""
            ALTER TABLE users ADD COLUMN parent_fcm_token TEXT
        """)
        print("✅ Added parent_fcm_token column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  parent_fcm_token column already exists")
        else:
            raise
    
    try:
        # Add notification preferences (JSON string)
        cursor.execute("""
            ALTER TABLE users ADD COLUMN notification_preferences TEXT DEFAULT '{}'
        """)
        print("✅ Added notification_preferences column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  notification_preferences column already exists")
        else:
            raise
    
    try:
        # Add last notification sent timestamp
        cursor.execute("""
            ALTER TABLE users ADD COLUMN last_notification_at TIMESTAMP
        """)
        print("✅ Added last_notification_at column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("ℹ️  last_notification_at column already exists")
        else:
            raise
    
    conn.commit()
    
    # Display updated schema
    print("\n📋 Updated users table schema:")
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    conn.close()
    print("\n✅ Migration completed successfully!")
    print("\n💡 Next steps:")
    print("  1. Set environment variables:")
    print("     export FCM_SERVER_KEY='your_firebase_key'")
    print("     export TWILIO_ACCOUNT_SID='your_twilio_sid'")
    print("     export TWILIO_AUTH_TOKEN='your_twilio_token'")
    print("     export TWILIO_PHONE_NUMBER='+1234567890'")
    print("  2. Install Twilio: pip install twilio")
    print("  3. Configure Firebase in frontend")

if __name__ == "__main__":
    migrate()
