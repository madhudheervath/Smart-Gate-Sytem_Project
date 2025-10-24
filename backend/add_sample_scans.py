#!/usr/bin/env python3
"""
Add sample scan logs for testing parent portal history
"""

from database import SessionLocal
from models import User, ScanLog
from datetime import datetime, timedelta
import random

db = SessionLocal()

print("\n" + "="*60)
print("Adding Sample Entry/Exit Scans for Testing")
print("="*60 + "\n")

# Get all students
students = db.query(User).filter(User.role == "student").all()

if not students:
    print("❌ No students found. Run add_students_with_parents.py first.")
    db.close()
    exit(1)

# Add sample scans for each student (last 7 days)
scan_types = ['entry', 'exit']
locations = ['Main Gate', 'North Gate', 'East Gate']

for student in students:
    print(f"\n📊 Adding scan history for {student.name} ({student.student_id})...")
    
    # Create 10-15 random scans over the last 7 days
    num_scans = random.randint(10, 15)
    
    for i in range(num_scans):
        # Random day in the last 7 days
        days_ago = random.randint(0, 6)
        
        # Random hour between 8 AM and 8 PM
        hour = random.randint(8, 20)
        minute = random.randint(0, 59)
        
        scan_time = datetime.now() - timedelta(days=days_ago)
        scan_time = scan_time.replace(hour=hour, minute=minute, second=0)
        
        # Alternate between entry and exit
        scan_type = 'entry' if i % 2 == 0 else 'exit'
        
        # Check if this scan already exists
        existing = db.query(ScanLog).filter(
            ScanLog.student_id == student.id,
            ScanLog.scan_time == scan_time
        ).first()
        
        if not existing:
            scan = ScanLog(
                student_id=student.id,
                scan_time=scan_time,
                pass_type=scan_type,
                result='success',
                details=f'Scanned at {random.choice(locations)} by Guard System'
            )
            db.add(scan)
            print(f"  ✅ {scan_type.upper():5} - {scan_time.strftime('%b %d, %I:%M %p')}")

db.commit()

print("\n" + "="*60)
print("✅ Sample scans added successfully!")
print("="*60 + "\n")

# Display summary
for student in students:
    count = db.query(ScanLog).filter(ScanLog.student_id == student.id).count()
    print(f"{student.name:15} ({student.student_id or 'N/A'}): {count} scans")

print("\n" + "="*60)
print("📋 Parents can now view entry/exit history!")
print("="*60 + "\n")

db.close()
