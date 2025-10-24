import sqlite3
from datetime import datetime, timedelta, timezone

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def now_ist():
    """Get current time in IST timezone"""
    return datetime.now(IST)

import os
print(f"\nCurrent directory: {os.getcwd()}")
db_path = 'backend/gatepass.db' if os.path.exists('backend/gatepass.db') else 'gatepass.db'
print(f"Using database: {db_path}")
print(f"Database exists: {os.path.exists(db_path)}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("\n" + "="*60)
print("DATABASE DEBUG - CHECKING PASS TYPES")
print("="*60)

print("\nChecking tables in database:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"  Tables: {[t[0] for t in tables]}")

print("\nRecent passes (last 5):")
cursor.execute('SELECT id, reason, pass_type, status, request_time FROM passes ORDER BY id DESC LIMIT 5')
for row in cursor.fetchall():
    print(f"  Pass #{row[0]:3d}: {row[1][:30]:30s} | type={row[2] if row[2] else 'NULL':5s} | status={row[3]}")

print("\nRecent scan logs (last 10):")
cursor.execute('SELECT id, pass_id, result, pass_type, scan_time FROM scan_logs ORDER BY id DESC LIMIT 10')
for row in cursor.fetchall():
    print(f"  Scan #{row[0]:3d}: pass_id={row[1]:3d} | result={row[2]:10s} | type={row[3] if row[3] else 'NULL':5s} | time={row[4]}")

# Check statistics for today
today_start_ist = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
print(f"\nStatistics (since {today_start_ist.strftime('%Y-%m-%d %H:%M:%S IST')}):")

cursor.execute(
    "SELECT pass_type, COUNT(*) FROM scan_logs WHERE scan_time >= ? AND result = 'success' GROUP BY pass_type",
    (today_start_ist.isoformat(),)
)

stats = cursor.fetchall()
if stats:
    for pass_type, count in stats:
        print(f"  {pass_type if pass_type else 'NULL':5s}: {count} scans today")
else:
    print("  No successful scans today.")

# Check all scan logs for today
cursor.execute(
    "SELECT COUNT(*) FROM scan_logs WHERE scan_time >= ?",
    (today_start_ist.isoformat(),)
)
total_today = cursor.fetchone()[0]
print(f"  TOTAL: {total_today} scans today (all types)")

print("\n" + "="*60)

conn.close()

