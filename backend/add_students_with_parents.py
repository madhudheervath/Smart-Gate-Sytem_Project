#!/usr/bin/env python3
"""
Add students with parent information for testing
"""

from database import SessionLocal, engine
from models import User, Base
from auth import hash_pwd
from datetime import datetime, timedelta

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Student data with parent information
students_data = [
    {
        "name": "Alice Chen",
        "email": "alice@uni.edu",
        "password": "alice123",
        "student_id": "S1001",
        "student_class": "CS-B",
        "parent_name": "Mary Chen",
        "parent_phone": "+12025550101",
        "phone": "+12025550102"
    },
    {
        "name": "Bob Müller",
        "email": "bob@uni.edu",
        "password": "bob123",
        "student_id": "S1002",
        "student_class": "CS-B",
        "parent_name": "James Müller",
        "parent_phone": "+12025550103",
        "phone": "+12025550104"
    },
    {
        "name": "Carol Osei",
        "email": "carol@uni.edu",
        "password": "carol123",
        "student_id": "S1003",
        "student_class": "CS-A",
        "parent_name": "Sarah Osei",
        "parent_phone": "+12025550105",
        "phone": "+12025550106"
    },
    {
        "name": "David Pham",
        "email": "david@uni.edu",
        "password": "david123",
        "student_id": "S1004",
        "student_class": "CS-A",
        "parent_name": "Robert Pham",
        "parent_phone": "+12025550107",
        "phone": "+12025550108"
    }
]

print("\n" + "="*60)
print("Adding Students with Parent Information")
print("="*60 + "\n")

for student_data in students_data:
    # Check if student already exists
    existing = db.query(User).filter(User.email == student_data["email"]).first()
    
    if existing:
        # Update existing student with parent info
        existing.parent_name = student_data["parent_name"]
        existing.parent_phone = student_data["parent_phone"]
        existing.phone = student_data["phone"]
        existing.student_id = student_data["student_id"]
        existing.student_class = student_data["student_class"]
        existing.valid_until = datetime.now() + timedelta(days=365)
        
        print(f"✅ Updated: {student_data['name']}")
        print(f"   Email: {student_data['email']}")
        print(f"   Student ID: {student_data['student_id']}")
        print(f"   Parent: {student_data['parent_name']}")
        print(f"   Parent Phone: {student_data['parent_phone']}")
        print()
    else:
        # Create new student
        new_student = User(
            name=student_data["name"],
            email=student_data["email"],
            pwd_hash=hash_pwd(student_data["password"]),
            role="student",
            active=True,
            student_id=student_data["student_id"],
            student_class=student_data["student_class"],
            valid_until=datetime.now() + timedelta(days=365),
            parent_name=student_data["parent_name"],
            parent_phone=student_data["parent_phone"],
            phone=student_data["phone"]
        )
        
        db.add(new_student)
        
        print(f"✅ Created: {student_data['name']}")
        print(f"   Email: {student_data['email']}")
        print(f"   Password: {student_data['password']}")
        print(f"   Student ID: {student_data['student_id']}")
        print(f"   Parent: {student_data['parent_name']}")
        print(f"   Parent Phone: {student_data['parent_phone']}")
        print()

db.commit()

print("="*60)
print("✅ All students added/updated successfully!")
print("="*60)

# Display summary
print("\n" + "="*60)
print("📋 STUDENT & PARENT CREDENTIALS FOR TESTING")
print("="*60 + "\n")

print("🎓 STUDENT PORTAL LOGIN")
print("-" * 60)
for student_data in students_data:
    print(f"\n{student_data['name']}:")
    print(f"  📧 Email: {student_data['email']}")
    print(f"  🔑 Password: {student_data['password']}")
    print(f"  🆔 Student ID: {student_data['student_id']}")
    print(f"  📚 Class: {student_data['student_class']}")

print("\n" + "-" * 60)
print("👨‍👩‍👧 PARENT INFORMATION")
print("-" * 60)
for student_data in students_data:
    print(f"\nParent of {student_data['name']}:")
    print(f"  👤 Name: {student_data['parent_name']}")
    print(f"  📱 Phone: {student_data['parent_phone']}")
    print("  🔗 Secure parent link must be generated from the student portal after login")

print("\n" + "="*60)
print("🧪 QUICK TEST INSTRUCTIONS")
print("="*60)
print("""
1. LOGIN AS STUDENT:
   - Go to: http://localhost:8080/frontend/student/index.html
   - Use any student credentials above
   - Open the Browser Alerts & Parent Access card
   - Save parent contact details
   - Copy the secure parent portal link

2. SETUP PARENT NOTIFICATIONS:
   - Use the secure parent portal link from the student portal
   - Student ID and student name should already be pre-filled
   - Enter parent name (e.g., Mary Chen)
   - Enter phone number (e.g., +12025550101)
   - Click "Continue Setup"

3. TEST NOTIFICATIONS:
   - Admin approves pass → Student sees approval state
   - Guard scans QR → Parent history updates
   - SMS alerts require backend Twilio configuration
""")

print("="*60 + "\n")

db.close()
