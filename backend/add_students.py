from database import Base, engine, SessionLocal
from models import User
from auth import hash_pwd
from datetime import datetime

# Create tables with new schema
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Student data from your team
students = [
    {
        "student_id": "U22CN361",
        "name": "Madhavi",
        "email": "u22cn361@cmrtc.ac.in",
        "student_class": "CSE 4 Year",
        "guardian_name": "Parent",
        "valid_until": "2026-05-31T23:59:59Z",
        "password": "madhavi123"
    },
    {
        "student_id": "U22CN362",
        "name": "Dhanush",
        "email": "u22cn362@cmrtc.ac.in",
        "student_class": "CSE 4 Year",
        "guardian_name": "Parent",
        "valid_until": "2026-05-31T23:59:59Z",
        "password": "dhanush123"
    },
    {
        "student_id": "U22CN414",
        "name": "Gowrishankar",
        "email": "u22cn414@cmrtc.ac.in",
        "student_class": "CSE 4 Year",
        "guardian_name": "Parent",
        "valid_until": "2026-05-31T23:59:59Z",
        "password": "gowri123"
    },
    {
        "student_id": "U22CN421",
        "name": "Tharun",
        "email": "u22cn421@cmrtc.ac.in",
        "student_class": "CSE 4 Year",
        "guardian_name": "Parent",
        "valid_until": "2026-05-31T23:59:59Z",
        "password": "tharun123"
    }
]

print("Adding students to database...")
print("=" * 60)

for student in students:
    # Check if student already exists
    existing = db.query(User).filter_by(student_id=student["student_id"]).first()
    if existing:
        print(f"⚠️  Student {student['student_id']} ({student['name']}) already exists - skipping")
        continue
    
    # Parse valid_until date
    valid_until = datetime.fromisoformat(student["valid_until"].replace('Z', '+00:00'))
    
    # Create new student user
    user = User(
        name=student["name"],
        email=student["email"],
        pwd_hash=hash_pwd(student["password"]),
        role="student",
        active=True,
        student_id=student["student_id"],
        student_class=student["student_class"],
        guardian_name=student["guardian_name"],
        valid_until=valid_until
    )
    
    db.add(user)
    print(f"✅ Added: {student['student_id']} - {student['name']} ({student['email']})")

db.commit()
db.close()

print("=" * 60)
print("\n✅ All students added successfully!")
print("\nLogin credentials:")
print("-" * 60)
for student in students:
    print(f"Student ID: {student['student_id']}")
    print(f"Name:       {student['name']}")
    print(f"Email:      {student['email']}")
    print(f"Password:   {student['password']}")
    print(f"Class:      {student['student_class']}")
    print(f"Valid Until: {student['valid_until']}")
    print("-" * 60)

