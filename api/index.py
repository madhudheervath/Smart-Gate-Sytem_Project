import os
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _configure_database() -> None:
    if os.getenv("DB_URL"):
        return

    for env_name in ("DATABASE_URL", "POSTGRES_URL"):
        env_value = os.getenv(env_name)
        if env_value:
            os.environ["DB_URL"] = env_value
            return

    bundled_candidates = [
        BACKEND_DIR / "gatepass.db",
        ROOT_DIR / "gatepass.db",
    ]
    bundled_db = next((candidate for candidate in bundled_candidates if candidate.exists()), None)
    target_db = Path("/tmp/gatepass.db")

    if bundled_db and not target_db.exists():
        shutil.copy2(bundled_db, target_db)

    os.environ["DB_URL"] = f"sqlite:///{target_db}" if target_db.exists() else "sqlite:////tmp/gatepass.db"


_configure_database()

from app import app as fastapi_app  # noqa: E402


app = fastapi_app
