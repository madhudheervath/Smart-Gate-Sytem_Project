from database import Base, engine, SessionLocal
from models import User
from auth import hash_pwd

Base.metadata.create_all(bind=engine)
db = SessionLocal()

users = [
    # Admin
    ("Admin Warden", "admin@uni.edu", "admin", "admin123", None),
    
    # Students
    ("Madhavi", "u22cn361@cmrtc.ac.in", "student", "madhavi123", "U22CN361"),
    ("Dhanush", "u22cn362@cmrtc.ac.in", "student", "dhanush123", "U22CN362"),
    ("Gowrishankar", "u22cn414@cmrtc.ac.in", "student", "gowri123", "U22CN414"),
    ("Tharun", "u22cn421@cmrtc.ac.in", "student", "tharun123", "U22CN421"),
    
    # Guards
    ("Gate Guard", "guard@uni.edu", "guard", "guard123", None),
    ("Gate Scanner", "scanner@uni.edu", "guard", "scanner123", None),
]

for name, email, role, pwd, sid in users:
    if not db.query(User).filter_by(email=email).first():
        user = User(name=name, email=email, role=role, pwd_hash=hash_pwd(pwd))
        if sid:
            user.student_id = sid
        db.add(user)

db.commit()
db.close()
print("Seeded users:")
for name, email, role, pwd, sid in users:
    print(f"  - {role.upper()}: {email} / {pwd} ({sid if sid else 'No ID'})")

