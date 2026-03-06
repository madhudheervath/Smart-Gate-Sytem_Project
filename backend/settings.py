from pydantic_settings import BaseSettings

from pydantic import AliasChoices, Field, field_validator
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_URL = f"sqlite:///{(BASE_DIR / 'gatepass.db').resolve()}"

class Settings(BaseSettings):
    SECRET_KEY: str = "change_me_32+_random_secret_key_here"
    JWT_SECRET: str = "change_me_jwt_secret_key_here"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    PARENT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30
    DB_URL: str = Field(
        default=DEFAULT_DB_URL,
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL", "POSTGRES_URL"),
    )
    QR_TTL_MINUTES: int = 15
    SELF_REGISTRATION_ENABLED: bool = False
    ACCOUNT_REQUESTS_ENABLED: bool = True
    FACE_AUTH_ENABLED: bool = True
    FACE_AUTH_BACKEND: str = "opencv"
    NOTIFICATIONS_ENABLED: bool = False
    GEOFENCE_ENABLED: bool = True

    @field_validator("DB_URL")
    @classmethod
    def fix_db_url(cls, v: str):
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

settings = Settings()  # env vars override in real deploy

