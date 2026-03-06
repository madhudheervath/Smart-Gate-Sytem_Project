import os

from database import Base, SessionLocal, engine
from models import User
from runtime_schema import ensure_runtime_schema
from seed import seed_demo_users


def _normalize_seed_mode(value: str) -> str:
    mode = (value or "if_empty").strip().lower()
    if mode in {"1", "true", "yes"}:
        return "always"
    if mode in {"0", "false", "no"}:
        return "never"
    if mode in {"always", "never", "if_empty"}:
        return mode
    print(f"⚠️  Unknown SMARTGATE_SEED_MODE={value!r}; defaulting to 'if_empty'")
    return "if_empty"


def bootstrap():
    mode = _normalize_seed_mode(os.getenv("SMARTGATE_SEED_MODE", "if_empty"))

    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        should_seed = mode == "always" or (mode == "if_empty" and user_count == 0)

        if should_seed:
            print(f"🌱 Seeding demo data (mode={mode}, existing_users={user_count})")
            summary = seed_demo_users(db)
            print(
                f"🌱 Seed complete: created={summary['created']}, "
                f"updated={summary['updated']}, total={summary['total']}"
            )
        else:
            print(f"⏭️  Skipping demo seed (mode={mode}, existing_users={user_count})")
    finally:
        db.close()


if __name__ == "__main__":
    bootstrap()
