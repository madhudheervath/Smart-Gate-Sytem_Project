"""
Settings for Vercel Serverless Deployment
Reads from environment variables for production
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change_me_32+_random_secret_key_here")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "change_me_jwt_secret_key_here")
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    
    # Database - Use PostgreSQL for Vercel
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        os.getenv("POSTGRES_URL", "sqlite:///./gatepass.db")
    )
    
    # QR Settings
    QR_TTL_MINUTES: int = int(os.getenv("QR_TTL_MINUTES", "15"))
    
    # Feature Flags
    FACE_AUTH_ENABLED: bool = os.getenv("FACE_AUTH_ENABLED", "false").lower() == "true"
    NOTIFICATIONS_ENABLED: bool = os.getenv("NOTIFICATIONS_ENABLED", "false").lower() == "true"
    GEOFENCE_ENABLED: bool = os.getenv("GEOFENCE_ENABLED", "true").lower() == "true"
    
    # Campus Location
    CAMPUS_LATITUDE: float = float(os.getenv("CAMPUS_LATITUDE", "31.7768"))
    CAMPUS_LONGITUDE: float = float(os.getenv("CAMPUS_LONGITUDE", "77.0144"))
    CAMPUS_RADIUS_KM: float = float(os.getenv("CAMPUS_RADIUS_KM", "2.0"))
    
    # API Base URL
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8080")
    
    # Environment
    ENVIRONMENT: str = os.getenv("NODE_ENV", "development")
    
    @property
    def DB_URL(self) -> str:
        """Compatibility with existing code"""
        return self.DATABASE_URL
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
