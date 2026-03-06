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
        "name": "Madhavi",
        "email": "u22cn361@cmrtc.ac.in",
        "password": "madhavi123",
        "student_id": "U22CN361",
        "student_class": "CSE-B",
        "parent_name": "Rajesh Kumar",
        "parent_phone": "+919876543210",
        "phone": "+919876543211"
    },
    {
        "name": "Dhanush",
        "email": "u22cn362@cmrtc.ac.in",
        "password": "dhanush123",
        "student_id": "U22CN362",
        "student_class": "CSE-B",
        "parent_name": "Suresh Reddy",
        "parent_phone": "+919876543212",
        "phone": "+919876543213"
    },
    {
        "name": "Gowrishankar",
        "email": "u22cn414@cmrtc.ac.in",
        "password": "gowri123",
        "student_id": "U22CN414",
        "student_class": "CSE-A",
        "parent_name": "Venkata Rao",
        "parent_phone": "+919876543214",
        "phone": "+919876543215"
    },
    {
        "name": "Tharun",
        "email": "u22cn421@cmrtc.ac.in",
        "password": "tharun123",
        "student_id": "U22CN421",
        "student_class": "CSE-A",
        "parent_name": "Ramesh Naidu",
        "parent_phone": "+919876543216",
        "phone": "+919876543217"
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
   - Enter parent name (e.g., Rajesh Kumar)
   - Enter phone number (e.g., +919876543210)
   - Click "Continue Setup"

3. TEST NOTIFICATIONS:
   - Admin approves pass → Student sees approval state
   - Guard scans QR → Parent history updates
   - SMS alerts require backend Twilio configuration
""")

print("="*60 + "\n")

db.close()
