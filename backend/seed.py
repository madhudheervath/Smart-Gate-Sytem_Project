from database import Base, engine, SessionLocal
from models import User
from auth import hash_pwd

DEMO_USERS = [
    ("Admin Warden", "admin@uni.edu", "admin", "admin123", None),
    ("Madhavi", "u22cn361@cmrtc.ac.in", "student", "madhavi123", "U22CN361"),
    ("Dhanush", "u22cn362@cmrtc.ac.in", "student", "dhanush123", "U22CN362"),
    ("Gowrishankar", "u22cn414@cmrtc.ac.in", "student", "gowri123", "U22CN414"),
    ("Tharun", "u22cn421@cmrtc.ac.in", "student", "tharun123", "U22CN421"),
    ("Gate Guard", "guard@uni.edu", "guard", "guard123", None),
    ("Gate Scanner", "scanner@uni.edu", "guard", "scanner123", None),
]


def seed_demo_users(db):
    created = 0
    updated = 0

    for name, email, role, pwd, sid in DEMO_USERS:
        user = db.query(User).filter_by(email=email).first()
        if user:
            user.name = name
            user.role = role
            user.pwd_hash = hash_pwd(pwd)
            if sid:
                user.student_id = sid
            updated += 1
            print(f"Updated user: {email}")
        else:
            user = User(name=name, email=email, role=role, pwd_hash=hash_pwd(pwd))
            if sid:
                user.student_id = sid
            db.add(user)
            created += 1
            print(f"Created user: {email}")

    db.commit()
    return {"created": created, "updated": updated, "total": len(DEMO_USERS)}


def seed_demo_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        return seed_demo_users(db)
    finally:
        db.close()


if __name__ == "__main__":
    summary = seed_demo_data()
    print("Seeded users:")
    for name, email, role, pwd, sid in DEMO_USERS:
        print(f"  - {role.upper()}: {email} / {pwd} ({sid if sid else 'No ID'})")
    print(
        f"Summary: created={summary['created']}, "
        f"updated={summary['updated']}, total={summary['total']}"
    )
