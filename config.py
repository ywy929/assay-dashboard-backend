from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Environment: "development" or "production"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str

    # JWT Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 120

    # Password hashing
    SALT_SIZE: int = 32
    HASH_SIZE: int = 32
    ITERATIONS: int = 100000

    # CORS - comma-separated origins for production
    CORS_ORIGINS: str = "http://localhost:8081"

    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Sync Settings
    SYNC_API_KEY: str = "change_this_to_a_secure_key"

    # APNs (Apple Push Notification service) - for direct iOS push
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_KEY_PATH: str = ""  # Path to .p8 file
    APNS_BUNDLE_ID: str = "com.brightnessassay.app"
    APNS_USE_SANDBOX: bool = True  # True for dev/TestFlight, False for App Store

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


settings = Settings()
