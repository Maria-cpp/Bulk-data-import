"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bulk_import_data"

    # File Upload
    BULK_IMPORT_MAX_FILE_SIZE: int = 52428800  # 50 MB in bytes
    BULK_IMPORT_PROCESSING_TIMEOUT: int = 300  # 5 minutes in seconds
    BULK_IMPORT_MAX_RETRIES: int = 3

    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

    # Tesseract OCR (Windows path, adjust for Linux/Docker)
    TESSERACT_CMD: str | None = None

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
