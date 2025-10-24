from database import Base, engine, SessionLocal
from models import User
from auth import hash_pwd

Base.metadata.create_all(bind=engine)
db = SessionLocal()

users = [
    ("Student One", "student1@uni.edu", "student", "s123456"),
    ("Student Two", "student2@uni.edu", "student", "s123456"),
    ("Admin Warden", "admin@uni.edu", "admin", "admin123"),
    ("Gate Scanner", "scanner@uni.edu", "guard", "scanner123"),
    ("Gate Guard", "guard@uni.edu", "guard", "guard123"),
]

for name, email, role, pwd in users:
    if not db.query(User).filter_by(email=email).first():
        db.add(User(name=name, email=email, role=role, pwd_hash=hash_pwd(pwd)))

db.commit()
db.close()
print("Seeded users:")
for name, email, role, pwd in users:
    print(f"  - {role.upper()}: {email} / {pwd}")

