from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = "change_me_32+_random_secret_key_here"
    JWT_SECRET: str = "change_me_jwt_secret_key_here"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12
    DB_URL: str = "sqlite:///./gatepass.db"
    QR_TTL_MINUTES: int = 15

settings = Settings()  # env vars override in real deploy

